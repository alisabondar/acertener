"""Time the encryption overhead of one patient-list page: decrypting 20 patients' fields.

No database needed: it measures the app's own cipher on realistic values.
Run from backend/:  uv run python -m scripts.time_decryption [--pages 500]
"""

import argparse
import statistics
import time

from cryptography.fernet import Fernet
from faker import Faker

from app.crypto import FernetFieldCipher

PAGE_SIZE = 20


def _patient(fake: Faker) -> list[str]:
    """The encrypted fields a list row shows or derives from (name, MRN, DOB, gender)."""
    return [
        fake.first_name(),
        fake.last_name(),
        f"MRN-{fake.random_number(digits=6, fix_len=True)}",
        fake.date_of_birth().isoformat(),
        fake.random_element(["female", "male"]),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", type=int, default=500)
    args = parser.parse_args()

    fake = Faker()
    Faker.seed(1)
    cipher = FernetFieldCipher([Fernet.generate_key()], Fernet.generate_key())
    pages = [
        [cipher.encrypt(value) for _ in range(PAGE_SIZE) for value in _patient(fake)]
        for _ in range(args.pages)
    ]

    samples = []
    for page in pages:
        start = time.perf_counter()
        for value in page:
            cipher.decrypt(value)
        samples.append((time.perf_counter() - start) * 1000)

    p50 = statistics.median(samples)
    p95 = statistics.quantiles(samples, n=20)[18]
    fields = len(pages[0])
    print(f"Decrypting one list page ({PAGE_SIZE} patients, {fields} fields):")
    print(f"  p50 {p50:.2f} ms   p95 {p95:.2f} ms   ({args.pages} pages)")


if __name__ == "__main__":
    main()
