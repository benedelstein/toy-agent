// Example VSCode extension for toy-agent integration
// Place this in .vscode/extensions/toy-agent/extension.js

const vscode = require('vscode');
const net = require('net');

let client = null;
let currentFile = null;

function activate(context) {
    console.log('Toy Agent extension activated');
    
    // Connect to toy-agent on startup
    connectToAgent();
    
    // Watch for active editor changes
    vscode.window.onDidChangeActiveTextEditor((editor) => {
        if (editor && editor.document) {
            const filePath = editor.document.fileName;
            if (filePath !== currentFile) {
                currentFile = filePath;
                sendFileEvent('opened', filePath);
            }
        }
    });
    
    // Watch for document changes
    vscode.workspace.onDidChangeTextDocument((event) => {
        if (event.document === vscode.window.activeTextEditor?.document) {
            sendFileEvent('modified', event.document.fileName);
        }
    });
    
    // Watch for file saves
    vscode.workspace.onDidSaveTextDocument((document) => {
        sendFileEvent('saved', document.fileName);
    });
}

function connectToAgent() {
    // Connect to toy-agent via TCP socket (you'd need to add a server to toy-agent)
    client = net.createConnection({ port: 9999, host: 'localhost' }, () => {
        console.log('Connected to toy-agent');
    });
    
    client.on('error', (err) => {
        console.error('Failed to connect to toy-agent:', err);
        // Retry connection after delay
        setTimeout(connectToAgent, 5000);
    });
}

function sendFileEvent(eventType, filePath) {
    if (client && client.writable) {
        const message = JSON.stringify({
            type: 'file_event',
            event: eventType,
            path: filePath,
            timestamp: new Date().toISOString()
        });
        
        client.write(message + '\n');
    }
}

function deactivate() {
    if (client) {
        client.end();
    }
}

module.exports = {
    activate,
    deactivate
};

// Package.json for the extension:
/*
{
    "name": "toy-agent-integration",
    "displayName": "Toy Agent Integration",
    "version": "0.0.1",
    "engines": {
        "vscode": "^1.74.0"
    },
    "main": "./extension.js",
    "contributes": {},
    "activationEvents": [
        "onStartupFinished"
    ]
}
*/