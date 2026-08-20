import { useEffect, useRef, useState } from "react";
import { Child, ChildSex, childrenApi } from "../api";
import DatePicker from "./DatePicker";
import Select from "./Select";
import { useConfirm } from "./ConfirmDialog";
import { todayIso } from "../lib/format";

const TODAY_ISO = todayIso();

const SEX_OPTIONS = [
  { value: "", label: "Unspecified" },
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
];

const toSex = (v: string): ChildSex | null => (v === "male" || v === "female" ? v : null);

interface ChildrenModalProps {
  onClose: () => void;
  childList: Child[];
  onChanged: () => void;
}

export default function ChildrenModal({
  onClose,
  childList,
  onChanged,
}: ChildrenModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const confirm = useConfirm();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDob, setEditDob] = useState("");
  const [editSex, setEditSex] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");

  const [newName, setNewName] = useState("");
  const [newDob, setNewDob] = useState("");
  const [newSex, setNewSex] = useState("");
  const [addBusy, setAddBusy] = useState(false);

  // Same focus trap + Esc/click-outside pattern as ProfileModal.
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    dialogRef.current?.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab" || !dialogRef.current) return;
      const focusables = dialogRef.current.querySelectorAll<HTMLElement>(
        'button, input, a[href], [tabindex]:not([tabindex="-1"])'
      );
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      previouslyFocused?.focus();
    };
  }, [onClose]);

  const startEdit = (c: Child) => {
    setError("");
    setEditingId(c.id);
    setEditName(c.name);
    setEditDob(c.date_of_birth ?? "");
    setEditSex(c.sex ?? "");
  };

  const saveEdit = async () => {
    if (!editingId || !editName.trim()) return;
    setBusyId(editingId);
    setError("");
    try {
      await childrenApi.update(editingId, editName.trim(), editDob || null, toSex(editSex));
      setEditingId(null);
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save changes");
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (c: Child) => {
    const ok = await confirm({
      title: `Remove ${c.name}?`,
      message: `This permanently deletes every prescription record saved for ${c.name} too. This can't be undone.`,
      confirmLabel: "Delete",
      danger: true,
    });
    if (!ok) return;
    setBusyId(c.id);
    setError("");
    try {
      await childrenApi.delete(c.id);
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't remove child");
    } finally {
      setBusyId(null);
    }
  };

  const newValid = newName.trim() && newDob && newSex;

  const add = async () => {
    if (!newValid) return;
    setAddBusy(true);
    setError("");
    try {
      await childrenApi.create(newName.trim(), newDob || null, toSex(newSex));
      setNewName("");
      setNewDob("");
      setNewSex("");
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't add child");
    } finally {
      setAddBusy(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal children-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="children-modal-title"
        tabIndex={-1}
        ref={dialogRef}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-head">
          <h3 id="children-modal-title">Children</h3>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="modal-body">
          {childList.length === 0 && (
            <p className="field-hint">
              Add a child to start assigning records to them.
            </p>
          )}

          {childList.map((c) => (
            <div className="profile-row" key={c.id}>
              {editingId === c.id ? (
                <span className="profile-inline-edit edit-child-fields">
                  <input
                    className="edit-child-name"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    autoFocus
                  />
                  <DatePicker
                    className="edit-child-dob"
                    value={editDob}
                    onChange={setEditDob}
                    max={TODAY_ISO}
                    ariaLabel="Date of birth"
                  />
                  <Select
                    className="field-select edit-child-sex"
                    value={editSex}
                    onChange={setEditSex}
                    options={SEX_OPTIONS}
                    ariaLabel="Sex"
                  />
                  <button
                    className="profile-row-action edit-child-submit"
                    onClick={saveEdit}
                    disabled={busyId === c.id}
                  >
                    Save
                  </button>
                </span>
              ) : (
                <>
                  <span className="profile-label" title={c.name}>
                    {c.name}
                  </span>
                  <span className="profile-inline-edit">
                    {c.date_of_birth && <span>{c.date_of_birth}</span>}
                    <button
                      className="profile-row-action"
                      onClick={() => startEdit(c)}
                    >
                      Edit
                    </button>
                    <button
                      className="profile-row-action"
                      onClick={() => remove(c)}
                      disabled={busyId === c.id}
                    >
                      Remove
                    </button>
                  </span>
                </>
              )}
            </div>
          ))}

          {error && <p className="field-hint error-text">{error}</p>}

          <div className="add-child-section">
            <div className="add-child-heading">Add a child</div>
            <div className="add-child-fields">
              <input
                className="add-child-name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Child's name"
              />
              <DatePicker
                className="add-child-dob"
                value={newDob}
                onChange={setNewDob}
                max={TODAY_ISO}
                ariaLabel="Date of birth"
              />
              <Select
                className="field-select add-child-sex"
                value={newSex}
                onChange={setNewSex}
                options={SEX_OPTIONS}
                ariaLabel="Sex"
              />
              <button
                className="profile-row-action add-child-submit"
                onClick={add}
                disabled={addBusy || !newValid}
              >
                Add
              </button>
            </div>
            <p className="field-hint">Name, date of birth, and sex are all required.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
