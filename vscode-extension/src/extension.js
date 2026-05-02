const vscode = require('vscode');
const axios = require('axios');

const BACKEND_URL = "http://localhost:8000";

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
    console.log('AI Buddy extension is now active!');

    let suggestDisposable = vscode.commands.registerCommand('aiBuddy.suggestCode', async function () {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showInformationMessage('Open a file to get suggestions.');
            return;
        }

        const text = editor.document.getText();
        
        try {
            const response = await axios.post(`${BACKEND_URL}/code/suggest`, {
                context: text.substring(0, 1000) // send snippet
            });

            const suggestion = response.data.suggestion;
            
            // Insert suggestion at cursor
            editor.edit(editBuilder => {
                editBuilder.insert(editor.selection.active, '\n' + suggestion + '\n');
            });

            vscode.window.showInformationMessage('AI Buddy: Recommendation added!');
        } catch (error) {
            vscode.window.showErrorMessage('AI Buddy Backend is not reachable. Is app.py running?');
        }
    });

    let errorDisposable = vscode.commands.registerCommand('aiBuddy.fixError', async function () {
        // Collect diagnostics (errors) in the active file
        const editor = vscode.window.activeTextEditor;
        if (!editor) return;

        const diagnostics = vscode.languages.getDiagnostics(editor.document.uri);
        if (diagnostics.length === 0) {
            vscode.window.showInformationMessage('No errors found!');
            return;
        }

        const errorMsg = diagnostics[0].message; // taking the first error
        try {
            const response = await axios.post(`${BACKEND_URL}/code/error`, {
                error: errorMsg
            });
            
            vscode.window.showInformationMessage(`AI Buddy Fix: ${response.data.fix}`);
        } catch (error) {
            vscode.window.showErrorMessage('AI Buddy Backend not reachable.');
        }
    });

    context.subscriptions.push(suggestDisposable);
    context.subscriptions.push(errorDisposable);
}

function deactivate() {}

module.exports = {
    activate,
    deactivate
}
