/**
 * Annotation Workstation Client Controller
 * Manages task queue, pacing timer, dynamic conditional fields, and API submission.
 */

// State
let taskQueue = [];
let currentIndex = 0;
let taskStartTime = Date.now();
let timerInterval = null;

// DOM Elements
const taskIdBadge = document.getElementById("task-id-badge");
const taskSkuBadge = document.getElementById("task-sku-badge");
const taskCatBadge = document.getElementById("task-cat-badge");
const queueProgress = document.getElementById("queue-progress");
const taskTimer = document.getElementById("task-timer");
const inspectionImage = document.getElementById("inspection-image");
const annotationForm = document.getElementById("annotation-form");
const conditionRadios = document.querySelectorAll('input[name="condition"]');
const openBoxBranch = document.getElementById("open-box-branch");
const damagedBranch = document.getElementById("damaged-branch");
const packagingSelect = document.getElementById("packaging-condition");
const sealSelect = document.getElementById("seal-condition");
const damageTypeSelect = document.getElementById("damage-type");
const damageSeveritySelect = document.getElementById("damage-severity");
const damageDescription = document.getElementById("damage-description");
const charCounter = document.getElementById("char-counter");
const validationErrors = document.getElementById("validation-errors");
const errorList = document.getElementById("error-list");
const toastBanner = document.getElementById("toast-banner");
const sopToggleBtn = document.getElementById("sop-toggle-btn");
const sopCloseBtn = document.getElementById("sop-close-btn");
const sopDrawer = document.getElementById("sop-drawer");
const skipBtn = document.getElementById("skip-btn");
const annotatorSelect = document.getElementById("annotator-select");

// Start Pacing Timer
function resetTimer() {
  if (timerInterval) clearInterval(timerInterval);
  taskStartTime = Date.now();
  updateTimerDisplay();
  timerInterval = setInterval(updateTimerDisplay, 1000);
}

function updateTimerDisplay() {
  const elapsedSeconds = Math.floor((Date.now() - taskStartTime) / 1000);
  const mins = String(Math.floor(elapsedSeconds / 60)).padStart(2, "0");
  const secs = String(elapsedSeconds % 60).padStart(2, "0");
  taskTimer.textContent = `${mins}:${secs}`;
}

// Fetch Tasks from API
async function loadTaskQueue() {
  try {
    const response = await fetch("/api/tasks");
    if (!response.ok) throw new Error("Failed to load tasks");
    taskQueue = await response.json();
    if (taskQueue.length === 0) {
      showToast("No pending tasks in queue.", "toast-success");
      queueProgress.textContent = "Queue Empty";
      return;
    }
    currentIndex = 0;
    renderCurrentTask();
  } catch (err) {
    showToast("Error connecting to AnnotationOps backend: " + err.message, "toast-error");
  }
}

// Render Current Task
function renderCurrentTask() {
  if (currentIndex >= taskQueue.length) {
    queueProgress.textContent = "All Tasks Completed!";
    taskIdBadge.textContent = "COMPLETE";
    taskSkuBadge.textContent = "---";
    taskCatBadge.textContent = "---";
    inspectionImage.src = "";
    annotationForm.classList.add("hidden");
    showToast("🎉 All queue tasks have been successfully processed.", "toast-success");
    return;
  }

  const task = taskQueue[currentIndex];
  taskIdBadge.textContent = task.task_id;
  taskSkuBadge.textContent = `SKU: ${task.sku || "N/A"}`;
  taskCatBadge.textContent = `Category: ${task.product_category || "General"}`;
  inspectionImage.src = `/api/images/${task.image_id}`;
  queueProgress.textContent = `${currentIndex + 1} of ${taskQueue.length} (${Math.round(((currentIndex) / taskQueue.length) * 100)}%)`;

  resetForm();
  resetTimer();
}

// Reset Form State
function resetForm() {
  annotationForm.reset();
  openBoxBranch.classList.add("hidden");
  damagedBranch.classList.add("hidden");
  validationErrors.classList.add("hidden");
  errorList.innerHTML = "";
  charCounter.textContent = "0 / 250 (min 10)";
  charCounter.style.color = "var(--text-muted)";
}

// Handle Conditional Visibility
conditionRadios.forEach(radio => {
  radio.addEventListener("change", (e) => {
    const selected = e.target.value;
    validationErrors.classList.add("hidden");

    if (selected === "NEW") {
      openBoxBranch.classList.add("hidden");
      damagedBranch.classList.add("hidden");
      clearOpenBoxFields();
      clearDamagedFields();
    } else if (selected === "OPEN_BOX") {
      openBoxBranch.classList.remove("hidden");
      damagedBranch.classList.add("hidden");
      clearDamagedFields();
    } else if (selected === "DAMAGED") {
      damagedBranch.classList.remove("hidden");
      openBoxBranch.classList.add("hidden");
      clearOpenBoxFields();
    }
  });
});

function clearOpenBoxFields() {
  packagingSelect.value = "";
  sealSelect.value = "";
}

function clearDamagedFields() {
  damageTypeSelect.value = "";
  damageSeveritySelect.value = "";
  damageDescription.value = "";
}

// Description Character Counter
damageDescription.addEventListener("input", (e) => {
  const len = e.target.value.trim().length;
  charCounter.textContent = `${len} / 250 (min 10)`;
  if (len > 0 && len < 10) {
    charCounter.style.color = "var(--accent-damaged)";
  } else {
    charCounter.style.color = "var(--text-muted)";
  }
});

// Client-Side Validation
function validateForm() {
  const errors = [];
  const selectedCond = document.querySelector('input[name="condition"]:checked');

  if (!selectedCond) {
    errors.push("Primary condition selection is required.");
    return errors;
  }

  const cond = selectedCond.value;
  if (cond === "OPEN_BOX") {
    if (!packagingSelect.value) errors.push("Packaging Condition is required for OPEN_BOX.");
    if (!sealSelect.value) errors.push("Seal Condition is required for OPEN_BOX.");
  } else if (cond === "DAMAGED") {
    if (!damageTypeSelect.value) errors.push("Damage Defect Type is required for DAMAGED.");
    if (!damageSeveritySelect.value) errors.push("Damage Severity is required for DAMAGED.");
    const desc = damageDescription.value.trim();
    if (!desc) {
      errors.push("Defect Description is required for DAMAGED.");
    } else if (desc.length < 10) {
      errors.push(`Defect Description must be at least 10 characters (currently ${desc.length}).`);
    }
  }

  return errors;
}

// Form Submission
annotationForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const errors = validateForm();

  if (errors.length > 0) {
    displayValidationErrors(errors);
    return;
  }

  const elapsedSeconds = Math.max(0.1, (Date.now() - taskStartTime) / 1000);
  const task = taskQueue[currentIndex];
  const selectedCond = document.querySelector('input[name="condition"]:checked').value;

  const payload = {
    task_id: task.task_id,
    image_id: task.image_id,
    annotator_id: annotatorSelect.value,
    condition: selectedCond,
    packaging_condition: selectedCond === "OPEN_BOX" ? packagingSelect.value : null,
    seal_condition: selectedCond === "OPEN_BOX" ? sealSelect.value : null,
    damage_type: selectedCond === "DAMAGED" ? damageTypeSelect.value : null,
    damage_severity: selectedCond === "DAMAGED" ? damageSeveritySelect.value : null,
    description: selectedCond === "DAMAGED" ? damageDescription.value.trim() : null,
    annotation_timestamp: new Date().toISOString(),
    processing_time_seconds: parseFloat(elapsedSeconds.toFixed(2)),
    schema_version: "1.0.0"
  };

  try {
    const res = await fetch("/api/annotate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const result = await res.json();
    if (!res.ok) {
      displayValidationErrors([result.detail || "Server rejected submission."]);
      return;
    }

    showToast(`✓ Task ${task.task_id} submitted (${elapsedSeconds.toFixed(1)}s)`, "toast-success");
    currentIndex++;
    renderCurrentTask();
  } catch (err) {
    displayValidationErrors(["Network error submitting annotation: " + err.message]);
  }
});

function displayValidationErrors(errors) {
  errorList.innerHTML = "";
  errors.forEach(err => {
    const li = document.createElement("li");
    li.textContent = err;
    errorList.appendChild(li);
  });
  validationErrors.classList.remove("hidden");
}

function showToast(message, typeClass) {
  toastBanner.textContent = message;
  toastBanner.className = `toast-banner ${typeClass}`;
  toastBanner.classList.remove("hidden");
  setTimeout(() => {
    toastBanner.classList.add("hidden");
  }, 4000);
}

// Skip / Escalate
skipBtn.addEventListener("click", () => {
  if (confirm("Skip this task and advance to the next in queue?")) {
    currentIndex++;
    renderCurrentTask();
  }
});

// SOP Drawer Toggle
sopToggleBtn.addEventListener("click", () => {
  sopDrawer.classList.toggle("hidden");
});
sopCloseBtn.addEventListener("click", () => {
  sopDrawer.classList.add("hidden");
});

// Initialize on Load
window.addEventListener("DOMContentLoaded", loadTaskQueue);
