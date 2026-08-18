import { useEffect } from "react";
import { Child, Medication, Prescription, emptyMedication } from "../api";
import { formatChildAge } from "../lib/format";

export interface PrescriptionFormProps {
  value: Prescription;
  onChange: (p: Prescription) => void;
  lowConfidence: string[];
  childList: Child[];
  onManageChildren: () => void;
}

function fieldFlag(lowConfidence: string[], path: string): boolean {
  return lowConfidence.includes(path);
}

export default function PrescriptionForm({
  value,
  onChange,
  lowConfidence,
  childList,
  onManageChildren,
}: PrescriptionFormProps) {
  const set = <K extends keyof Prescription>(key: K, v: Prescription[K]) =>
    onChange({ ...value, [key]: v });

  const setMed = (i: number, key: keyof Medication, v: string) => {
    const medications = value.medications.map((m, idx) =>
      idx === i ? { ...m, [key]: v } : m
    );
    onChange({ ...value, medications });
  };

  const addMed = () =>
    onChange({ ...value, medications: [...value.medications, emptyMedication()] });

  const removeMed = (i: number) =>
    onChange({
      ...value,
      medications: value.medications.filter((_, idx) => idx !== i),
    });

  const flagged = (field: string) => (fieldFlag(lowConfidence, field) ? "flagged" : "");

  // Fills child_age from the child's date_of_birth + the prescription's
  // date_of_visit, but only while the field is still empty - OCR extraction
  // and any value the user has already typed both win over this. Re-runs
  // whenever the child or date changes, so picking a date after the child
  // (or switching children) still fills it in, not just the first render.
  useEffect(() => {
    if (value.child_age || !value.child_id || !value.date_of_visit) return;
    const child = childList.find((c) => c.id === value.child_id);
    if (!child?.date_of_birth) return;
    const computed = formatChildAge(child.date_of_birth, value.date_of_visit);
    if (computed) set("child_age", computed);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value.child_id, value.date_of_visit, childList]);

  return (
    <div className="review-fields">
      {value.medications.map((m, i) => (
        <div className="review-med-block" key={i}>
          {value.medications.length > 1 && (
            <div className="review-med-block-head">
              <span>Medication {i + 1}</span>
              <button
                type="button"
                className="ghost danger"
                onClick={() => removeMed(i)}
                aria-label="Remove medication"
              >
                ×
              </button>
            </div>
          )}
          <div className="review-grid">
            <label className={flagged(`medications.${i}.name`)}>
              MEDICATION
              <input
                value={m.name}
                onChange={(e) => setMed(i, "name", e.target.value)}
                placeholder="e.g. Amoxicillin"
              />
              {fieldFlag(lowConfidence, `medications.${i}.name`) && (
                <span className="field-hint">Please check</span>
              )}
            </label>
            <label className={flagged(`medications.${i}.dosage`)}>
              STRENGTH / DOSE
              <input
                value={m.dosage}
                onChange={(e) => setMed(i, "dosage", e.target.value)}
                placeholder="e.g. 250mg"
              />
              {fieldFlag(lowConfidence, `medications.${i}.dosage`) && (
                <span className="field-hint">Please check</span>
              )}
            </label>
            <label className={flagged(`medications.${i}.frequency`)}>
              HOW OFTEN
              <input
                value={m.frequency}
                onChange={(e) => setMed(i, "frequency", e.target.value)}
                placeholder="e.g. 3 times a day"
              />
              {fieldFlag(lowConfidence, `medications.${i}.frequency`) && (
                <span className="field-hint">Please check</span>
              )}
            </label>
            <label className={flagged(`medications.${i}.duration`)}>
              COURSE
              <input
                value={m.duration}
                onChange={(e) => setMed(i, "duration", e.target.value)}
                placeholder="e.g. 7 days"
              />
              {fieldFlag(lowConfidence, `medications.${i}.duration`) && (
                <span className="field-hint">Please check</span>
              )}
            </label>
          </div>
        </div>
      ))}
      <button type="button" className="ghost add-row" onClick={addMed}>
        + Add another medication
      </button>

      <div className="review-grid">
        <label className={flagged("doctor_name")}>
          PRESCRIBER
          <input
            value={value.doctor_name}
            onChange={(e) => set("doctor_name", e.target.value)}
            placeholder="Dr. ..."
          />
          {fieldFlag(lowConfidence, "doctor_name") && (
            <span className="field-hint">Please check</span>
          )}
        </label>
        <label className={flagged("date_of_visit")}>
          DATE ON PRESCRIPTION
          <input
            type="date"
            value={value.date_of_visit ?? ""}
            onChange={(e) => set("date_of_visit", e.target.value || null)}
          />
          {fieldFlag(lowConfidence, "date_of_visit") && (
            <span className="field-hint">Please check</span>
          )}
        </label>
      </div>

      {childList.length > 0 ? (
        <label className="stacked-field">
          Child *
          <select
            value={value.child_id ?? ""}
            onChange={(e) => set("child_id", e.target.value || null)}
          >
            <option value="" disabled>
              Select a child
            </option>
            {childList.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <button type="button" className="child-manage-link" onClick={onManageChildren}>
            + Add another child
          </button>
        </label>
      ) : (
        <div className="no-children-callout">
          <p>You need to add a child before you can save a record.</p>
          <button type="button" className="ghost" onClick={onManageChildren}>
            + Add a child
          </button>
        </div>
      )}

      <div className="review-grid">
        <label>
          Child age
          <input
            value={value.child_age}
            onChange={(e) => set("child_age", e.target.value)}
            placeholder="e.g. 3 years"
          />
        </label>
        <label>
          Child weight
          <input
            value={value.child_weight}
            onChange={(e) => set("child_weight", e.target.value)}
            placeholder="e.g. 14 kg"
          />
        </label>
      </div>

      <label className="stacked-field">
        Complaint
        <textarea
          value={value.complaint}
          onChange={(e) => set("complaint", e.target.value)}
          rows={2}
        />
      </label>
      <label className="stacked-field">
        Diagnosis
        <textarea
          value={value.diagnosis}
          onChange={(e) => set("diagnosis", e.target.value)}
          rows={2}
        />
      </label>
      <label className="stacked-field">
        Additional notes
        <textarea
          value={value.additional_notes}
          onChange={(e) => set("additional_notes", e.target.value)}
          rows={3}
        />
      </label>
    </div>
  );
}

export function validatePrescription(p: Prescription): string[] {
  const errors: string[] = [];
  if (!p.child_id) {
    errors.push("Choose which child this record belongs to.");
  }
  if (!p.medications.some((m) => m.name.trim())) {
    errors.push("At least one medication name is required.");
  }
  if (p.date_of_visit) {
    const d = new Date(`${p.date_of_visit}T00:00:00`);
    if (Number.isNaN(d.getTime())) {
      errors.push("Date on prescription isn't a valid date.");
    } else if (d.getTime() > Date.now()) {
      errors.push("Date on prescription can't be in the future.");
    }
  }
  return errors;
}
