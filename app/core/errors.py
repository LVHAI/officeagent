class OfficeAgentError(Exception):
    """Base exception for recoverable application failures."""


class AgentError(OfficeAgentError):
    pass


class ToolError(OfficeAgentError):
    pass


class RetrievalError(OfficeAgentError):
    pass


class ModelError(OfficeAgentError):
    pass


class MCPError(ToolError):
    pass


class InfrastructureError(OfficeAgentError):
    pass
