"""LSP server integration for editor awareness."""
import asyncio
import json
from typing import Optional, Dict, Any
from pylsp import lsp
from pylsp.server import LanguageServer


class AgentLSPServer(LanguageServer):
    """Custom LSP server that notifies agent of file events."""
    
    def __init__(self, agent_callback, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent_callback = agent_callback
        self.active_document: Optional[str] = None
        
    def m_text_document__did_open(self, **params) -> None:
        """Called when a document is opened in the editor."""
        uri = params['textDocument']['uri']
        file_path = uri.replace('file://', '')
        self.active_document = file_path
        self.agent_callback('opened', file_path)
        
    def m_text_document__did_change(self, **params) -> None:
        """Called when a document is modified."""
        uri = params['textDocument']['uri']
        file_path = uri.replace('file://', '')
        # Get the actual changes if needed
        content_changes = params.get('contentChanges', [])
        self.agent_callback('modified', file_path, changes=content_changes)
        
    def m_text_document__did_focus(self, **params) -> None:
        """Called when user focuses on a document (custom extension)."""
        uri = params['textDocument']['uri']
        file_path = uri.replace('file://', '')
        self.active_document = file_path
        self.agent_callback('focused', file_path)


def start_lsp_server(agent_callback):
    """Start the LSP server for editor integration."""
    server = AgentLSPServer(agent_callback)
    server.start_tcp('127.0.0.1', 8080)
    return server