import { format, parseISO } from "date-fns";
import { useState } from "react";

import { api } from "@/api";
import { queryKeys, useApiMutation } from "@/api/queries";
import type { components } from "@/api/schema";
import { useCurrentUser, usePermission } from "@/auth/context";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";

import { useChartNotes } from "./chartData";
import { WriteError } from "./WriteError";

type Note = components["schemas"]["NoteOut"];

export function NotesTab({ patientId }: { patientId: string }) {
  const { me } = useCurrentUser();
  const canWrite = usePermission("WRITE_NOTES_AND_VITALS");
  const notes = useChartNotes(patientId, true);
  // The draft being composed: an existing draft's id once it's been saved.
  const [composing, setComposing] = useState<{ id: string | null; content: string } | null>(null);
  const [deleting, setDeleting] = useState<Note | null>(null);

  return (
    <div className="space-y-4">
      {canWrite && !composing && (
        <Button onClick={() => setComposing({ id: null, content: "" })}>New note</Button>
      )}
      {composing && (
        <Composer
          patientId={patientId}
          draft={composing}
          onChange={setComposing}
          onDone={() => setComposing(null)}
        />
      )}
      {notes.data ? (
        notes.data.items.length > 0 ? (
          <ul aria-label="Notes" className="space-y-3">
            {notes.data.items.map((note) => {
              const myDraft = note.status === "draft" && note.author_id === me.id;
              return (
                <li key={note.id} className="space-y-2 rounded-xl border bg-card p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 text-[13px]">
                    <span>
                      <span className="font-medium">{note.author_name}</span>
                      <span className="text-muted-foreground">
                        {" "}
                        ·{" "}
                        {format(
                          parseISO(note.finalized_at ?? note.updated_at),
                          "MMM d, yyyy h:mm a",
                        )}
                      </span>
                    </span>
                    {note.status === "draft" && (
                      <span className="rounded-full bg-muted px-2 py-0.5 text-[12px] font-medium">
                        Draft
                      </span>
                    )}
                  </div>
                  <p className="text-[14px] whitespace-pre-wrap">{note.content}</p>
                  {myDraft && (
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setComposing({ id: note.id, content: note.content })}
                      >
                        Continue editing
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-severe"
                        aria-label="Delete draft"
                        onClick={() => setDeleting(note)}
                      >
                        Delete
                      </Button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-[14px] text-muted-foreground">No notes yet</p>
        )
      ) : (
        <Skeleton className="h-24 w-full rounded-xl" />
      )}
      <DeleteDraft patientId={patientId} note={deleting} onClose={() => setDeleting(null)} />
    </div>
  );
}

function Composer({
  patientId,
  draft,
  onChange,
  onDone,
}: {
  patientId: string;
  draft: { id: string | null; content: string };
  onChange: (draft: { id: string | null; content: string }) => void;
  onDone: () => void;
}) {
  const invalidate = [queryKeys.patients.chart(patientId)];
  // Create the draft the first time, then update it.
  const save = useApiMutation(
    async (content: string) =>
      draft.id
        ? api.PATCH("/api/v1/notes/{note_id}", {
            params: { path: { note_id: draft.id } },
            body: { content },
          })
        : api.POST("/api/v1/patients/{patient_id}/notes", {
            params: { path: { patient_id: patientId } },
            body: { content },
          }),
    { invalidate },
  );
  const finalize = useApiMutation(
    (noteId: string) =>
      api.POST("/api/v1/notes/{note_id}/finalize", { params: { path: { note_id: noteId } } }),
    { invalidate },
  );

  const saveDraft = async () => {
    const saved = await save.mutateAsync(draft.content);
    if (saved) onChange({ id: saved.id, content: draft.content });
    return saved;
  };

  return (
    <div className="space-y-3 rounded-xl border bg-card p-4">
      <Textarea
        aria-label="Note"
        value={draft.content}
        onChange={(event) => onChange({ ...draft, content: event.target.value })}
        rows={6}
        placeholder="Subjective, objective, assessment, plan…"
      />
      <WriteError error={save.error ?? finalize.error} action="write notes" />
      <div className="flex gap-2">
        <Button
          variant="outline"
          disabled={save.isPending}
          onClick={() => void saveDraft().catch(() => {})}
        >
          Save draft
        </Button>
        <Button
          disabled={save.isPending || finalize.isPending || !draft.content.trim()}
          onClick={() =>
            void saveDraft()
              .then(async (saved) => {
                if (saved) await finalize.mutateAsync(saved.id);
                onDone();
              })
              .catch(() => {})
          }
        >
          Finalize
        </Button>
        <Button variant="ghost" onClick={onDone}>
          Close
        </Button>
      </div>
    </div>
  );
}

function DeleteDraft({
  patientId,
  note,
  onClose,
}: {
  patientId: string;
  note: Note | null;
  onClose: () => void;
}) {
  const remove = useApiMutation(
    (noteId: string) =>
      api.DELETE("/api/v1/notes/{note_id}", { params: { path: { note_id: noteId } } }),
    { invalidate: [queryKeys.patients.chart(patientId)] },
  );
  return (
    <AlertDialog open={note !== null} onOpenChange={(open) => !open && onClose()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete this draft?</AlertDialogTitle>
          <AlertDialogDescription>
            It hasn't been finalized, so it isn't part of the record yet.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <WriteError error={remove.error} action="delete this note" />
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          {/* A plain button, not AlertDialogAction: it stays open until the delete lands. */}
          <Button
            variant="destructive"
            disabled={remove.isPending}
            onClick={() =>
              note &&
              void remove
                .mutateAsync(note.id)
                .then(onClose)
                .catch(() => {})
            }
          >
            Delete
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
