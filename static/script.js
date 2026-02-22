const codeEditor = document.getElementById("codeEditor");
const runBtn = document.getElementById("runBtn");
const fixBtn = document.getElementById("fixBtn");
const clearBtn = document.getElementById("clearBtn");
const applyFixBtn = document.getElementById("applyFixBtn");

const statusBadge = document.getElementById("statusBadge");
const loadingSpinner = document.getElementById("loadingSpinner");
const charCount = document.getElementById("charCount");

const outputText = document.getElementById("outputText");
const errorMeta = document.getElementById("errorMeta");
const tracebackText = document.getElementById("tracebackText");
const codePreview = document.getElementById("codePreview");
const explanationText = document.getElementById("explanationText");
const suggestionText = document.getElementById("suggestionText");
const fixedCodePreview = document.getElementById("fixedCodePreview");
const resultPane = document.getElementById("resultPane");

let latestFixedCode = "";

const starterCode = [
    "# Write Python code and click Run Code",
    "name = input('Your name: ')",
    "print('Hello ' + name)",
].join("\n");

if (!codeEditor.value.trim()) {
    codeEditor.value = starterCode;
}

updateCharCount();
setStatus("Ready", "idle");
resetPanels();

codeEditor.addEventListener("input", updateCharCount);
runBtn.addEventListener("click", handleRun);
fixBtn.addEventListener("click", handleAIFix);
clearBtn.addEventListener("click", handleClear);
applyFixBtn.addEventListener("click", applyFixCode);

function updateCharCount() {
    charCount.textContent = `${codeEditor.value.length} chars`;
}

function setStatus(text, mode) {
    statusBadge.textContent = text;
    statusBadge.className = `status-badge ${mode}`;
}

function setBusy(isBusy, label) {
    runBtn.disabled = isBusy;
    fixBtn.disabled = isBusy;
    clearBtn.disabled = isBusy;

    if (isBusy) {
        setStatus(label || "Working...", "running");
        loadingSpinner.classList.remove("hidden");
    } else {
        loadingSpinner.classList.add("hidden");
    }
}

function resetPanels() {
    outputText.textContent = "Run code to see output.";
    errorMeta.innerHTML = "<span class='key'>Error Type</span><span>None</span><span class='key'>Line</span><span>None</span><span class='key'>Message</span><span>None</span>";
    tracebackText.textContent = "No traceback.";
    codePreview.textContent = "No error line to highlight.";
    explanationText.textContent = "No explanation yet.";
    suggestionText.textContent = "";
    fixedCodePreview.textContent = "No fixed code yet.";
    applyFixBtn.classList.add("hidden");
    latestFixedCode = "";
}

function escapeHtml(text) {
    return String(text || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function autoScrollToResults() {
    resultPane.scrollTo({ top: resultPane.scrollHeight, behavior: "smooth" });
}

async function postJson(url, payload, timeoutMs = 60000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
        const response = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
            signal: controller.signal,
        });

        let data;
        try {
            data = await response.json();
        } catch (_err) {
            data = { ok: false, error: "Server returned invalid JSON." };
        }

        if (!response.ok) {
            throw new Error(data.error || `Request failed with status ${response.status}`);
        }

        return data;
    } finally {
        clearTimeout(timer);
    }
}

function renderCodePreview(sourceCode, errorLine) {
    const lines = String(sourceCode || "").split("\n");
    const htmlLines = lines.map((line, index) => {
        const lineNumber = index + 1;
        const safeLine = escapeHtml(line);
        if (lineNumber === errorLine) {
            return `<span class="error-line"><span class="line-number">${lineNumber}</span>${safeLine}</span>`;
        }
        return `<span class="normal-line"><span class="line-number">${lineNumber}</span>${safeLine}</span>`;
    });

    codePreview.innerHTML = htmlLines.join("\n") || "No code.";
}

function renderExecution(execution, explanation, sourceCode) {
    if (!execution) {
        return;
    }

    if (execution.success) {
        setStatus("Success", "success");
        outputText.textContent = execution.stdout || execution.output || "Program finished with no output.";
        errorMeta.innerHTML = "<span class='key'>Error Type</span><span>None</span><span class='key'>Line</span><span>None</span><span class='key'>Message</span><span>None</span>";
        tracebackText.textContent = "No traceback.";
        codePreview.textContent = "No error line to highlight.";
        explanationText.textContent = "Code executed successfully.";
        suggestionText.textContent = "";
        return;
    }

    setStatus("Error", "error");

    const errorType = execution.error_type || "ExecutionError";
    const errorLine = execution.error_line ?? "Unknown";
    const errorMessage = execution.error_message || "Unknown error";

    errorMeta.innerHTML = [
        `<span class='key'>Error Type</span><span>${escapeHtml(errorType)}</span>`,
        `<span class='key'>Line</span><span>${escapeHtml(errorLine)}</span>`,
        `<span class='key'>Message</span><span>${escapeHtml(errorMessage)}</span>`,
    ].join("");

    tracebackText.textContent = execution.traceback || execution.stderr || "No traceback available.";
    renderCodePreview(sourceCode, execution.error_line);

    if (explanation) {
        explanationText.textContent = explanation.explanation || "No explanation available.";
        suggestionText.textContent = explanation.suggestion ? `Suggestion: ${explanation.suggestion}` : "";
    } else {
        explanationText.textContent = "No explanation available.";
        suggestionText.textContent = "";
    }
}

function renderFixedCodePreview(code, showApply = false) {
    if (code && code.trim()) {
        fixedCodePreview.textContent = code;
        latestFixedCode = code;
        if (showApply) {
            applyFixBtn.classList.remove("hidden");
        }
        return;
    }

    fixedCodePreview.textContent = "No fixed code yet.";
    latestFixedCode = "";
    applyFixBtn.classList.add("hidden");
}

function applyFixCode() {
    const fixedCode = document.getElementById("fixedCodePreview").innerText;
    document.getElementById("codeEditor").value = fixedCode;
    latestFixedCode = fixedCode;
    updateCharCount();
    renderFixedCodePreview("", false);
    setStatus("Fixed code applied. Click Run Code.", "success");
}

async function handleRun() {
    const code = codeEditor.value;
    if (!code.trim()) {
        setStatus("Please enter code", "error");
        return;
    }

    setBusy(true, "Running code...");

    try {
        const data = await postJson("/run", { code });
        renderExecution(data.execution, data.explanation, code);
    } catch (error) {
        setStatus("Request failed", "error");
        outputText.textContent = "";
        tracebackText.textContent = error.message;
        explanationText.textContent = "Could not communicate with backend.";
        suggestionText.textContent = "Verify Flask server is running and try again.";
    } finally {
        setBusy(false);
        autoScrollToResults();
    }
}

async function handleAIFix() {
    const code = codeEditor.value;
    if (!code.trim()) {
        setStatus("Please enter code", "error");
        return;
    }

    setBusy(true, "Generating AI fix...");

    try {
        const data = await postJson("/ai_fix", { code, model: "llama3" }, 120000);

        if (data.ai_warning) {
            suggestionText.textContent = data.ai_warning;
        }

        // Show current error context first
        if (data.original_execution) {
            renderExecution(data.original_execution, data.final_explanation, code);
        }

        if (data.fixed_code && data.fixed_code.trim()) {
            const changed = data.fixed_code.trim() !== code.trim();
            renderFixedCodePreview(data.fixed_code, changed);

            if (changed) {
                setStatus("AI fix ready. Click Apply Fixed Code.", "success");
            } else if (data.fixed_execution && data.fixed_execution.success) {
                setStatus("Code already valid", "success");
            } else {
                setStatus("No fix generated", "error");
            }
        } else {
            renderFixedCodePreview("", false);
            setStatus("No fix generated", "error");
        }
    } catch (error) {
        setStatus("AI fix failed", "error");
        suggestionText.textContent = "Ensure Ollama is running: ollama serve, then try again.";
        tracebackText.textContent = error.message;
    } finally {
        setBusy(false);
        autoScrollToResults();
    }
}

function handleClear() {
    codeEditor.value = "";
    updateCharCount();
    resetPanels();
    setStatus("Cleared", "idle");
}
