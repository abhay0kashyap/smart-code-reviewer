const codeEditor = document.getElementById("codeEditor");
const runBtn = document.getElementById("runBtn");
const aiFixBtn = document.getElementById("aiFixBtn");
const applyFixBtn = document.getElementById("applyFixBtn");
const clearBtn = document.getElementById("clearBtn");

const loader = document.getElementById("loader");
const statusBadge = document.getElementById("statusBadge");

const outputPanel = document.getElementById("outputPanel");
const errorType = document.getElementById("errorType");
const errorMessage = document.getElementById("errorMessage");
const errorLine = document.getElementById("errorLine");
const tracebackPanel = document.getElementById("tracebackPanel");
const highlightPanel = document.getElementById("highlightPanel");
const explanationPanel = document.getElementById("explanationPanel");
const fixedCodePreview = document.getElementById("fixedCodePreview");

let latestFixedCode = "";
let latestErrorText = "";

if (!codeEditor.value.trim()) {
    codeEditor.value = [
        "# Write Python code",
        "name = 'Abhay'",
        "print('Hello', name/)",
    ].join("\n");
}

runBtn.addEventListener("click", runCode);
aiFixBtn.addEventListener("click", aiFixCode);
applyFixBtn.addEventListener("click", applyFixCode);
clearBtn.addEventListener("click", clearAll);

async function postJson(url, body) {
    const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });

    let payload;
    try {
        payload = await response.json();
    } catch {
        payload = {};
    }

    if (!response.ok) {
        throw new Error(payload.error || `Request failed (${response.status})`);
    }

    return payload;
}

function setLoading(loading, statusText = "Ready") {
    loader.classList.toggle("hidden", !loading);
    runBtn.disabled = loading;
    aiFixBtn.disabled = loading;
    clearBtn.disabled = loading;
    statusBadge.textContent = loading ? "Processing..." : statusText;
}

function renderRunResult(payload, sourceCode) {
    const execution = payload.execution || {};
    const explanation = payload.explanation || null;

    if (execution.success) {
        latestErrorText = "";
        outputPanel.textContent = execution.stdout || execution.output || "Program executed with no output.";
        errorType.textContent = "None";
        errorMessage.textContent = "None";
        errorLine.textContent = "None";
        tracebackPanel.textContent = "No traceback.";
        highlightPanel.textContent = "No highlighted line.";
        explanationPanel.textContent = "Code executed successfully.";
        return;
    }

    outputPanel.textContent = execution.stdout || "No program output.";
    errorType.textContent = execution.error_type || "ExecutionError";
    errorMessage.textContent = execution.error_message || "Unknown error";
    errorLine.textContent = execution.error_line ?? "Unknown";
    tracebackPanel.textContent = execution.traceback || execution.stderr || "No traceback.";
    latestErrorText = execution.traceback || execution.error || execution.error_message || "";
    explanationPanel.textContent = explanation?.explanation || "No explanation available.";

    renderHighlightedLine(sourceCode, execution.error_line);
}

function renderHighlightedLine(code, lineNumber) {
    const lines = String(code || "").split("\n");
    if (!lineNumber || lineNumber < 1 || lineNumber > lines.length) {
        highlightPanel.textContent = "No highlighted line.";
        return;
    }

    const html = lines
        .map((line, idx) => {
            const n = idx + 1;
            const escaped = escapeHtml(line);
            if (n === lineNumber) {
                return `<span class="highlight-line">${n}: ${escaped}</span>`;
            }
            return `${n}: ${escaped}`;
        })
        .join("\n");

    highlightPanel.innerHTML = html;
}

function renderFixedPreview(autofix) {
    const fix = autofix || {};
    if (fix.fix_available && fix.fixed_code && fix.fixed_code.trim()) {
        latestFixedCode = fix.fixed_code;
        fixedCodePreview.textContent = fix.fixed_code;
        applyFixBtn.disabled = false;
        return;
    }

    latestFixedCode = "";
    fixedCodePreview.textContent = "No fixed code preview yet.";
    applyFixBtn.disabled = true;
}

async function runCode() {
    const code = codeEditor.value;
    setLoading(true);

    try {
        const runPayload = await postJson("/run", { code });
        renderRunResult(runPayload, code);
        statusBadge.textContent = runPayload.execution?.success ? "Run successful" : "Run failed";
    } catch (err) {
        outputPanel.textContent = "";
        tracebackPanel.textContent = String(err.message || err);
        statusBadge.textContent = "Run request failed";
    } finally {
        setLoading(false, statusBadge.textContent);
    }
}

async function aiFixCode() {
    const code = codeEditor.value;
    setLoading(true);

    try {
        let errorText = latestErrorText;
        if (!errorText) {
            const runPayload = await postJson("/run", { code });
            renderRunResult(runPayload, code);

            if (runPayload.execution?.success) {
                renderFixedPreview({ fix_available: false });
                statusBadge.textContent = "Code already valid";
                return;
            }

            errorText =
                runPayload.execution?.traceback ||
                runPayload.execution?.error ||
                runPayload.execution?.error_message ||
                "";
        }

        const fixPayload = await postJson("/ai_fix", { code, error: errorText });
        renderFixedPreview(fixPayload);

        if (fixPayload.fix_available) {
            statusBadge.textContent = "Fixed code generated";
        } else {
            statusBadge.textContent = "No auto fix available";
        }
    } catch (err) {
        fixedCodePreview.textContent = `Auto-fix failed: ${String(err.message || err)}`;
        applyFixBtn.disabled = true;
        statusBadge.textContent = "Auto-fix request failed";
    } finally {
        setLoading(false, statusBadge.textContent);
    }
}

function applyFixCode() {
    if (!latestFixedCode) {
        return;
    }

    codeEditor.value = latestFixedCode;
    fixedCodePreview.textContent = "Fixed code applied to editor.";
    latestFixedCode = "";
    applyFixBtn.disabled = true;
    statusBadge.textContent = "Fixed code applied. Run again.";
}

function clearAll() {
    codeEditor.value = "";
    outputPanel.textContent = "Run code to see output.";
    errorType.textContent = "None";
    errorMessage.textContent = "None";
    errorLine.textContent = "None";
    tracebackPanel.textContent = "No traceback.";
    highlightPanel.textContent = "No highlighted line.";
    explanationPanel.textContent = "No explanation yet.";
    fixedCodePreview.textContent = "No fixed code preview yet.";
    latestFixedCode = "";
    applyFixBtn.disabled = true;
    statusBadge.textContent = "Cleared";
}

function escapeHtml(text) {
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
