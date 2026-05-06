import * as vscode from 'vscode';

// JARVIS API Client
class JarvisClient {
    private serverUrl: string;
    private token: string;

    constructor() {
        const config = vscode.workspace.getConfiguration('jarvis');
        this.serverUrl = config.get('serverUrl') || 'http://localhost:8001';
        this.token = config.get('authToken') || '';
    }

    async login(): Promise<string> {
        const resp = await fetch(`${this.serverUrl}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ method: 'vscode_extension' }),
        });
        const data = await resp.json() as any;
        if (data.success) {
            this.token = data.token;
            const config = vscode.workspace.getConfiguration('jarvis');
            await config.update('authToken', data.token, vscode.ConfigurationTarget.Global);
            return data.token;
        }
        throw new Error(data.message || 'Login failed');
    }

    async action(req: {
        action: string;
        code?: string;
        language?: string;
        cursor_line?: number;
        file_path?: string;
        prompt?: string;
    }): Promise<string> {
        if (!this.token) {
            await this.login();
        }

        const resp = await fetch(`${this.serverUrl}/api/vscode/action`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-JARVIS-TOKEN': this.token,
            },
            body: JSON.stringify(req),
        });

        if (resp.status === 401) {
            await this.login();
            return this.action(req);
        }

        const data = await resp.json() as any;
        return data.response || data.error || 'No response';
    }
}

let jarvis: JarvisClient;
let outputChannel: vscode.OutputChannel;

export function activate(context: vscode.ExtensionContext) {
    jarvis = new JarvisClient();
    outputChannel = vscode.window.createOutputChannel('JARVIS');

    outputChannel.appendLine('JARVIS Neural Interface activated.');
    outputChannel.appendLine('All systems online. Ready to assist, Sir.');

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('jarvis.chat', chatCommand),
        vscode.commands.registerCommand('jarvis.explain', explainCommand),
        vscode.commands.registerCommand('jarvis.fix', fixCommand),
        vscode.commands.registerCommand('jarvis.refactor', refactorCommand),
        vscode.commands.registerCommand('jarvis.generate', generateCommand),
        vscode.commands.registerCommand('jarvis.complete', completeCommand),
    );

    // Register inline completion provider
    const config = vscode.workspace.getConfiguration('jarvis');
    if (config.get('autoComplete')) {
        const provider = vscode.languages.registerInlineCompletionItemProvider(
            { pattern: '**' },
            new JarvisCompletionProvider()
        );
        context.subscriptions.push(provider);
    }

    // Register sidebar webview
    const sidebarProvider = new JarvisSidebarProvider(context.extensionUri);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('jarvis.chatView', sidebarProvider)
    );

    vscode.window.showInformationMessage('JARVIS AI Assistant is online.');
}

// ── Commands ────────────────────────────────────────────────────────────────

async function chatCommand() {
    const prompt = await vscode.window.showInputBox({
        prompt: 'Ask JARVIS anything...',
        placeHolder: 'e.g., How do I implement a binary search tree?',
    });
    if (!prompt) return;

    const editor = vscode.window.activeTextEditor;
    const code = editor?.document.getText(editor.selection) || undefined;
    const language = editor?.document.languageId || 'text';

    await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: 'JARVIS is thinking...' },
        async () => {
            const response = await jarvis.action({ action: 'chat', prompt, code, language });
            showResponse('Chat', response);
        }
    );
}

async function explainCommand() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.selection.isEmpty) {
        vscode.window.showWarningMessage('Select code for JARVIS to explain.');
        return;
    }

    const code = editor.document.getText(editor.selection);
    const language = editor.document.languageId;

    await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: 'JARVIS analyzing code...' },
        async () => {
            const response = await jarvis.action({ action: 'explain', code, language });
            showResponse('Explanation', response);
        }
    );
}

async function fixCommand() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.selection.isEmpty) {
        vscode.window.showWarningMessage('Select code for JARVIS to fix.');
        return;
    }

    const code = editor.document.getText(editor.selection);
    const language = editor.document.languageId;

    const errorMsg = await vscode.window.showInputBox({
        prompt: 'Describe the error/issue (optional)',
        placeHolder: 'e.g., TypeError on line 5',
    });

    await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: 'JARVIS fixing bugs...' },
        async () => {
            const response = await jarvis.action({
                action: 'fix', code, language, prompt: errorMsg || undefined,
            });
            showResponse('Bug Fix', response);
        }
    );
}

async function refactorCommand() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.selection.isEmpty) {
        vscode.window.showWarningMessage('Select code for JARVIS to refactor.');
        return;
    }

    const code = editor.document.getText(editor.selection);
    const language = editor.document.languageId;

    const goal = await vscode.window.showInputBox({
        prompt: 'Refactoring goal (optional)',
        placeHolder: 'e.g., improve performance, add type hints',
    });

    await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: 'JARVIS refactoring...' },
        async () => {
            const response = await jarvis.action({
                action: 'refactor', code, language, prompt: goal || undefined,
            });
            showResponse('Refactored Code', response);
        }
    );
}

async function generateCommand() {
    const prompt = await vscode.window.showInputBox({
        prompt: 'What should JARVIS generate?',
        placeHolder: 'e.g., A REST API endpoint for user registration',
    });
    if (!prompt) return;

    const editor = vscode.window.activeTextEditor;
    const language = editor?.document.languageId || 'python';

    await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: 'JARVIS generating code...' },
        async () => {
            const response = await jarvis.action({ action: 'generate', prompt, language });
            showResponse('Generated Code', response);
        }
    );
}

async function completeCommand() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return;

    const position = editor.selection.active;
    const document = editor.document;
    const lineCount = Math.min(position.line + 1, 50);
    const startLine = Math.max(0, position.line - lineCount);
    const code = document.getText(new vscode.Range(startLine, 0, position.line, position.character));
    const language = document.languageId;

    await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: 'JARVIS completing...' },
        async () => {
            const response = await jarvis.action({
                action: 'complete',
                code,
                language,
                cursor_line: position.line,
                file_path: document.fileName,
            });

            // Insert completion at cursor
            const cleanResponse = response.replace(/```[\w]*\n?/g, '').replace(/```$/g, '').trim();
            editor.edit(editBuilder => {
                editBuilder.insert(position, cleanResponse);
            });
        }
    );
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function showResponse(title: string, response: string) {
    outputChannel.clear();
    outputChannel.appendLine(`═══ JARVIS: ${title} ═══`);
    outputChannel.appendLine('');
    outputChannel.appendLine(response);
    outputChannel.show(true);
}

// ── Inline Completion Provider ──────────────────────────────────────────────

class JarvisCompletionProvider implements vscode.InlineCompletionItemProvider {
    private debounceTimer: NodeJS.Timeout | undefined;

    async provideInlineCompletionItems(
        document: vscode.TextDocument,
        position: vscode.Position,
    ): Promise<vscode.InlineCompletionItem[]> {
        // Only trigger after typing pauses
        if (this.debounceTimer) clearTimeout(this.debounceTimer);

        return new Promise((resolve) => {
            this.debounceTimer = setTimeout(async () => {
                try {
                    const lineCount = Math.min(position.line + 1, 30);
                    const startLine = Math.max(0, position.line - lineCount);
                    const code = document.getText(
                        new vscode.Range(startLine, 0, position.line, position.character)
                    );

                    if (code.trim().length < 10) {
                        resolve([]);
                        return;
                    }

                    const response = await jarvis.action({
                        action: 'complete',
                        code,
                        language: document.languageId,
                        cursor_line: position.line,
                        file_path: document.fileName,
                    });

                    const cleanResponse = response.replace(/```[\w]*\n?/g, '').replace(/```$/g, '').trim();
                    if (cleanResponse) {
                        resolve([new vscode.InlineCompletionItem(cleanResponse)]);
                    } else {
                        resolve([]);
                    }
                } catch {
                    resolve([]);
                }
            }, 1500);
        });
    }
}

// ── Sidebar Webview ─────────────────────────────────────────────────────────

class JarvisSidebarProvider implements vscode.WebviewViewProvider {
    constructor(private readonly extensionUri: vscode.Uri) {}

    resolveWebviewView(webviewView: vscode.WebviewView) {
        webviewView.webview.options = { enableScripts: true };
        webviewView.webview.html = this.getHtml();

        webviewView.webview.onDidReceiveMessage(async (message) => {
            if (message.type === 'chat') {
                const editor = vscode.window.activeTextEditor;
                const code = editor?.document.getText(editor.selection) || undefined;
                const language = editor?.document.languageId || 'text';

                const response = await jarvis.action({
                    action: 'chat',
                    prompt: message.text,
                    code,
                    language,
                });

                webviewView.webview.postMessage({ type: 'response', text: response });
            }
        });
    }

    private getHtml(): string {
        return `<!DOCTYPE html>
<html>
<head>
<style>
    body { font-family: 'JetBrains Mono', monospace; background: #020617; color: #cffafe; padding: 12px; font-size: 12px; }
    #messages { overflow-y: auto; max-height: calc(100vh - 80px); }
    .msg { margin-bottom: 8px; padding: 6px 8px; border-left: 2px solid; }
    .msg-user { border-color: #06b6d4; color: #67e8f9; }
    .msg-jarvis { border-color: #22c55e; color: #86efac; }
    #input-row { display: flex; gap: 4px; position: fixed; bottom: 8px; left: 12px; right: 12px; }
    input { flex: 1; background: #0f172a; border: 1px solid rgba(6,182,212,0.3); color: #cffafe; padding: 6px 8px; font-size: 11px; outline: none; }
    input:focus { border-color: #06b6d4; }
    button { background: rgba(6,182,212,0.2); border: 1px solid rgba(6,182,212,0.4); color: #06b6d4; padding: 6px 12px; cursor: pointer; font-size: 11px; }
    button:hover { background: rgba(6,182,212,0.3); }
</style>
</head>
<body>
    <div id="messages"></div>
    <div id="input-row">
        <input id="chat-input" placeholder="Ask JARVIS..." />
        <button onclick="send()">Send</button>
    </div>
    <script>
        const vscode = acquireVsCodeApi();
        const messages = document.getElementById('messages');
        const input = document.getElementById('chat-input');

        input.addEventListener('keydown', (e) => { if (e.key === 'Enter') send(); });

        function send() {
            const text = input.value.trim();
            if (!text) return;
            addMessage('user', text);
            vscode.postMessage({ type: 'chat', text });
            input.value = '';
        }

        function addMessage(role, text) {
            const div = document.createElement('div');
            div.className = 'msg msg-' + role;
            div.textContent = (role === 'jarvis' ? 'JARVIS: ' : '> ') + text;
            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
        }

        window.addEventListener('message', (event) => {
            if (event.data.type === 'response') {
                addMessage('jarvis', event.data.text);
            }
        });
    </script>
</body>
</html>`;
    }
}

export function deactivate() {
    outputChannel?.dispose();
}
