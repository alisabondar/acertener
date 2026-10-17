import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, fields
from datetime import date
from enum import StrEnum
from typing import Any

from sqlalchemy import ColumnElement, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import FieldCipher, normalize
from app.db.models import Patient, PatientNamePrefix

DEFAULT_SEARCH_LIMIT = 50
PREFIX_MIN_LENGTH = 3
_MRN_UNIQUE_CONSTRAINT = "uq_patients_mrn_fp"


class Purpose(StrEnum):
    """Fingerprint purposes. Part of every stored fingerprint, so never rename one."""

    LAST_NAME = "last_name"
    DOB = "dob"
    MRN = "mrn"
    LAST_NAME_PREFIX = "last_name_prefix"
    FIRST_NAME_PREFIX = "first_name_prefix"


PREFIX_PURPOSES = {"last_name": Purpose.LAST_NAME_PREFIX, "first_name": Purpose.FIRST_NAME_PREFIX}


def name_prefixes(value: str) -> set[str]:
    """Every prefix of at least PREFIX_MIN_LENGTH characters, plus the whole name.

    Including the whole name lets short names ("Li") match exactly through the same index.
    """
    name = normalize(value)
    return {name[:end] for end in range(PREFIX_MIN_LENGTH, len(name) + 1)} | {name}


class DuplicateMrnError(Exception):
    """Another patient already has this MRN. Carries no identifiers."""


@dataclass(frozen=True)
class NewPatient:
    first_name: str
    last_name: str
    mrn: str
    dob: date
    gender: str | None = None
    phone: str | None = None
    email: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None


UPDATABLE_FIELDS = frozenset(
    {f.name for f in fields(NewPatient)}
    | {"status", "last_visit_at", "archived_at", "archived_by", "archive_reason"}
)


class PatientRepository:
    """Patient persistence. Derives fingerprints and birth_year so they can't drift."""

    def __init__(self, session: AsyncSession, cipher: FieldCipher) -> None:
        self._session = session
        self._cipher = cipher

    async def create(self, data: NewPatient) -> Patient:
        patient = Patient(**asdict(data))
        self._derive_search_fields(patient, data.last_name, data.dob, data.mrn)
        async with self._savepoint():
            self._session.add(patient)
            await self._session.flush()
            for field, purpose in PREFIX_PURPOSES.items():
                self._add_prefixes(patient.id, purpose, getattr(data, field))
        return patient

    async def get(self, patient_id: uuid.UUID) -> Patient | None:
        return await self._session.get(Patient, patient_id)

    async def update(self, patient_id: uuid.UUID, **changes: Any) -> Patient:
        unknown = set(changes) - UPDATABLE_FIELDS
        if unknown:
            raise ValueError(f"fields can't be updated directly: {', '.join(sorted(unknown))}")
        patient = await self._session.get_one(Patient, patient_id)
        async with self._savepoint():
            for name, value in changes.items():
                setattr(patient, name, value)
            self._derive_search_fields(
                patient, changes.get("last_name"), changes.get("dob"), changes.get("mrn")
            )
            for field, purpose in PREFIX_PURPOSES.items():
                if field in changes:
                    await self._session.execute(
                        delete(PatientNamePrefix).where(
                            PatientNamePrefix.patient_id == patient.id,
                            PatientNamePrefix.purpose == purpose,
                        )
                    )
                    self._add_prefixes(patient.id, purpose, changes[field])
        return patient

    async def search(
        self,
        *,
        last_name: str | None = None,
        first_name: str | None = None,
        dob: date | None = None,
        include_archived: bool = False,
        limit: int = DEFAULT_SEARCH_LIMIT,
    ) -> list[Patient]:
        """Prefix match on last/first name (case- and spacing-insensitive) and/or exact DOB.

        Terms shorter than PREFIX_MIN_LENGTH only match names that short (e.g. "Li").
        """
        query = select(Patient).where(*self.search_conditions(last_name, first_name, dob))
        if not include_archived:
            query = query.where(Patient.archived_at.is_(None))
        # Ciphertext can't be sorted by name, so the most recently seen come first.
        query = query.order_by(Patient.last_visit_at.desc().nulls_last(), Patient.id).limit(limit)
        return list(await self._session.scalars(query))

    async def find_likely_duplicates(self, last_name: str, dob: date) -> list[uuid.UUID]:
        """Current patients with the same last name and DOB (a warning, not proof)."""
        rows = await self._session.scalars(
            select(Patient.id).where(
                Patient.last_name_fp == self._cipher.fingerprint(Purpose.LAST_NAME, last_name),
                Patient.dob_fp == self._fingerprint_dob(dob),
                Patient.archived_at.is_(None),
            )
        )
        return list(rows)

    def search_conditions(
        self,
        last_name: str | None,
        first_name: str | None,
        dob: date | None,
        mrn: str | None = None,
    ) -> list[ColumnElement[bool]]:
        """WHERE clauses for a name-prefix, DOB, and/or exact MRN search, via fingerprints."""
        if last_name is None and dob is None and mrn is None:
            raise ValueError("search needs last_name, dob, or mrn")
        conditions: list[ColumnElement[bool]] = []
        for purpose, term in (
            (Purpose.LAST_NAME_PREFIX, last_name),
            (Purpose.FIRST_NAME_PREFIX, first_name),
        ):
            if term is not None:
                conditions.append(
                    Patient.id.in_(
                        select(PatientNamePrefix.patient_id).where(
                            PatientNamePrefix.purpose == purpose,
                            PatientNamePrefix.fp == self._cipher.fingerprint(purpose, term),
                        )
                    )
                )
        if dob is not None:
            conditions.append(Patient.dob_fp == self._fingerprint_dob(dob))
        if mrn is not None:
            conditions.append(Patient.mrn_fp == self._cipher.fingerprint(Purpose.MRN, mrn))
        return conditions

    def _derive_search_fields(
        self, patient: Patient, last_name: str | None, dob: date | None, mrn: str | None
    ) -> None:
        if last_name is not None:
            patient.last_name_fp = self._cipher.fingerprint(Purpose.LAST_NAME, last_name)
        if dob is not None:
            patient.dob_fp = self._fingerprint_dob(dob)
            patient.birth_year = dob.year
        if mrn is not None:
            patient.mrn_fp = self._cipher.fingerprint(Purpose.MRN, mrn)

    def _add_prefixes(self, patient_id: uuid.UUID, purpose: Purpose, value: str) -> None:
        self._session.add_all(
            PatientNamePrefix(
                patient_id=patient_id, purpose=purpose, fp=self._cipher.fingerprint(purpose, p)
            )
            for p in name_prefixes(value)
        )

    def _fingerprint_dob(self, dob: date) -> bytes:
        return self._cipher.fingerprint(Purpose.DOB, dob.isoformat())

    @asynccontextmanager
    async def _savepoint(self) -> AsyncIterator[None]:
        """Apply changes inside a savepoint and flush, so a failure leaves the session clean."""
        try:
            async with self._session.begin_nested():
                yield
                await self._session.flush()
        except IntegrityError as exc:
            if _MRN_UNIQUE_CONSTRAINT in str(exc.orig):
                raise DuplicateMrnError from None
            raise
