// API configuration - loaded from config.js written at deploy time
let API_BASE_URL = window.APP_CONFIG?.API_BASE_URL || null;
// Normalize scheme to match the page to avoid mixed-content blocking
if (API_BASE_URL) {
  try {
    const u = new URL(API_BASE_URL, window.location.origin);
    u.protocol = window.location.protocol;
    API_BASE_URL = u.toString().replace(/\/$/, "");
  } catch (e) {
    // leave as-is if not a valid URL
  }
}

// Timer state
let timerState = {
  isRunning: false,
  startTime: null,
  elapsedTime: 0,
  intervalId: null,
};

// DOM elements
const projectInput = document.getElementById("project");
const nameInput = document.getElementById("name");
const timerDisplay = document.getElementById("timerDisplay");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const saveBtn = document.getElementById("saveBtn");
const refreshBtn = document.getElementById("refreshBtn");
const entriesList = document.getElementById("entriesList");

// Initialize the app
document.addEventListener("DOMContentLoaded", async function () {
  if (!API_BASE_URL) {
    console.error(
      "API endpoint missing. Ensure config.js is generated during deploy.",
    );
    return;
  }
  console.log("Using API endpoint:", API_BASE_URL);

  loadTimeEntries();
  updateTimerDisplay();

  // Event listeners
  startBtn.addEventListener("click", startTimer);
  stopBtn.addEventListener("click", stopTimer);
  saveBtn.addEventListener("click", saveEntry);
  refreshBtn.addEventListener("click", loadTimeEntries);
});

// Dynamic configuration removed; rely on config.js populated during deployment

function startTimer() {
  if (!projectInput.value.trim() || !nameInput.value.trim()) {
    alert("Please enter both project and task name before starting the timer.");
    return;
  }

  timerState.isRunning = true;
  timerState.startTime = new Date();
  timerState.elapsedTime = 0;

  // Update UI
  startBtn.disabled = true;
  stopBtn.disabled = false;
  projectInput.disabled = true;
  nameInput.disabled = true;

  // Start the timer interval
  timerState.intervalId = setInterval(updateTimerDisplay, 1000);
}

function stopTimer() {
  timerState.isRunning = false;

  if (timerState.intervalId) {
    clearInterval(timerState.intervalId);
    timerState.intervalId = null;
  }

  // Update UI
  stopBtn.disabled = true;
  saveBtn.disabled = false;
}

function resetTimer() {
  timerState.isRunning = false;
  timerState.startTime = null;
  timerState.elapsedTime = 0;

  if (timerState.intervalId) {
    clearInterval(timerState.intervalId);
    timerState.intervalId = null;
  }

  // Update UI
  startBtn.disabled = false;
  stopBtn.disabled = true;
  saveBtn.disabled = true;
  projectInput.disabled = false;
  nameInput.disabled = false;

  updateTimerDisplay();
}

function updateTimerDisplay() {
  let totalSeconds = timerState.elapsedTime;

  if (timerState.isRunning && timerState.startTime) {
    const now = new Date();
    totalSeconds = Math.floor((now - timerState.startTime) / 1000);
    timerState.elapsedTime = totalSeconds;
  }

  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  timerDisplay.textContent = `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
}

async function saveEntry() {
  if (!timerState.startTime) {
    alert("No timer session to save.");
    return;
  }

  const endTime = new Date();
  const durationMinutes = Math.floor(timerState.elapsedTime / 60);

  const timeEntry = {
    project: projectInput.value.trim(),
    name: nameInput.value.trim(),
    start_time: timerState.startTime.toISOString(),
    end_time: endTime.toISOString(),
    duration: durationMinutes,
  };

  try {
    const response = await fetch(`${API_BASE_URL}/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(timeEntry),
    });

    if (response.ok) {
      alert("Time entry saved successfully!");

      // Clear form and reset timer
      projectInput.value = "";
      nameInput.value = "";
      resetTimer();

      // Refresh the entries list
      loadTimeEntries();
    } else {
      const errorData = await response.json();
      alert(`Error saving time entry: ${errorData.error || "Unknown error"}`);
    }
  } catch (error) {
    console.error("Error saving time entry:", error);
    alert("Error saving time entry. Make sure LocalStack is running.");
  }
}

async function loadTimeEntries() {
  try {
    console.log("Loading time entries from:", `${API_BASE_URL}/`);
    const response = await fetch(`${API_BASE_URL}/`);

    if (response.ok) {
      const entries = await response.json();
      console.log("Loaded entries:", entries);
      displayEntries(entries);
    } else {
      console.error("Failed to load time entries, status:", response.status);
      const errorText = await response.text();
      console.error("Error response:", errorText);
      entriesList.innerHTML = `<p>Error loading time entries (${response.status}). Make sure LocalStack is running.</p>`;
    }
  } catch (error) {
    console.error("Error loading time entries:", error);
    entriesList.innerHTML = `<p>Error loading time entries: ${error.message}. Make sure LocalStack is running.</p>`;
  }
}

function displayEntries(entries) {
  if (entries.length === 0) {
    entriesList.innerHTML = "<p>No time entries found.</p>";
    return;
  }

  entriesList.innerHTML = entries
    .map(
      (entry) => `
        <div class="entry" data-id="${entry.id}">
            <h3>${entry.project} - ${entry.name}</h3>
            <p><strong>Start:</strong> ${formatDateTime(entry.start_time)}</p>
            <p><strong>End:</strong> ${formatDateTime(entry.end_time)}</p>
            <p><strong>Duration:</strong> ${entry.duration} minutes</p>
            <div class="entry-buttons">
                <button class="edit-btn" onclick="editEntry('${entry.id}')">Edit</button>
                <button class="delete-btn" onclick="deleteEntry('${entry.id}')">Delete</button>
            </div>
        </div>
    `,
    )
    .join("");
}

function formatDateTime(dateTimeString) {
  if (!dateTimeString) return "N/A";
  const date = new Date(dateTimeString);
  return date.toLocaleString();
}

async function deleteEntry(id) {
  if (confirm("Are you sure you want to delete this entry?")) {
    try {
      const response = await fetch(`${API_BASE_URL}/${id}`, {
        method: "DELETE",
      });

      if (response.ok) {
        loadTimeEntries();
      } else {
        alert("Error deleting entry");
      }
    } catch (error) {
      console.error("Error deleting entry:", error);
      alert("Error deleting entry. Make sure LocalStack is running.");
    }
  }
}

function editEntry(id) {
  // For now, just show an alert. Could implement a modal form later
  alert("Edit functionality coming soon!");
}
