const vscode = require('vscode');
const axios = require('axios');
const cp = require('child_process');

const BACKEND_URL = "http://localhost:8000";

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
    console.log('AI Buddy extension is now active!');

    // Create a dedicated output channel
    let outputChannel = vscode.window.createOutputChannel("AI Buddy Output");

    let suggestDisposable = vscode.commands.registerCommand('aiBuddy.suggestCode', async function () {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showInformationMessage('Open a file to get suggestions.');
            return;
        }

        const selection = editor.selection;
        const selectedText = editor.document.getText(selection);
        const text = editor.document.getText();
        
        // If user highlighted code, only send that. Otherwise, send the entire file.
        const codeContext = selectedText || text;
        
        try {
            const response = await axios.post(`${BACKEND_URL}/code/suggest`, {
                context: codeContext 
            });

            const suggestion = response.data.suggestion;
            
            // Reverted typewriter effect because VS Code's native auto-indentation 
            // corrupts the Python formatting when typing character-by-character.
            editor.edit(editBuilder => {
                if (!selection.isEmpty) {
                    editBuilder.replace(selection, suggestion);
                } else {
                    const fullRange = new vscode.Range(
                        editor.document.positionAt(0),
                        editor.document.positionAt(text.length)
                    );
                    editBuilder.replace(fullRange, suggestion);
                }
            });

            vscode.window.showInformationMessage('AI Buddy: Code replaced successfully!');
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
            await axios.post(`${BACKEND_URL}/avatar/trigger`, { state: 'defeated' });
            
            const response = await axios.post(`${BACKEND_URL}/code/error`, {
                error: errorMsg
            });
            
            vscode.window.showInformationMessage(`AI Buddy Fix: ${response.data.fix}`);
        } catch (error) {
            vscode.window.showErrorMessage('AI Buddy Backend not reachable.');
        }
    });

    let runCodeDisposable = vscode.commands.registerCommand('aiBuddy.runCode', async function () {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showInformationMessage('Open a Python file to run.');
            return;
        }
        
        const filePath = editor.document.uri.fsPath;
        // Save the file before running
        await editor.document.save();

        // Show the Output Terminal Panel
        outputChannel.show(true); 
        outputChannel.appendLine(`\n>>> Running: ${filePath}`);
        
        // Let's set it to thinking while it evaluates
        try { await axios.post(`${BACKEND_URL}/avatar/trigger`, { state: 'talking' }); } catch(e){}

        cp.exec(`python "${filePath}"`, async (error, stdout, stderr) => {
            if (error) {
                // Print to Output panel
                outputChannel.appendLine(stderr || error.message);
                
                // If code failed, trigger defeated/error animation!
                try { await axios.post(`${BACKEND_URL}/avatar/trigger`, { state: 'error' }); } catch(e){}
                vscode.window.showErrorMessage(`Execution Failed - See Output Panel`);
            } else {
                // Print to Output panel
                outputChannel.appendLine(stdout);
                
                // If code ran successfully, trigger celebration!
                try { await axios.post(`${BACKEND_URL}/avatar/trigger`, { state: 'success' }); } catch(e){}
                vscode.window.showInformationMessage(`Execution Success - See Output Panel`);
            }
        });
    });

    context.subscriptions.push(suggestDisposable);
    context.subscriptions.push(errorDisposable);
    context.subscriptions.push(runCodeDisposable);
}

function deactivate() {}

module.exports = {
    activate,
    deactivate
}
