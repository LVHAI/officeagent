from app.core.config import settings
from app.tools.mcp_client import MCPClient, MCPServer
from app.tools.skills import Skill, SkillRegistry


def build_skill_registry() -> SkillRegistry:
    clients = {
        "crm": MCPClient(MCPServer("crm", settings.crm_mcp_url)),
        "database": MCPClient(MCPServer("database", settings.database_mcp_url)),
        "knowledge": MCPClient(MCPServer("knowledge", settings.knowledge_mcp_url)),
        "report": MCPClient(MCPServer("report", settings.report_mcp_url)),
    }
    registry = SkillRegistry(clients)
    registry.register(
        Skill(
            name="customer_analysis",
            description="查询客户信息、订单历史和客户价值",
            server="crm",
            tools=("customer_query",),
        )
    )
    registry.register(
        Skill(
            name="sales_data_analysis",
            description="查询企业销售汇总数据",
            server="database",
            tools=("sales_summary",),
        )
    )
    registry.register(
        Skill(
            name="knowledge_search",
            description="搜索企业知识库",
            server="knowledge",
            tools=("knowledge_search",),
        )
    )
    registry.register(
        Skill(
            name="report_generation",
            description="生成分析报告",
            server="report",
            tools=("report_generate",),
        )
    )
    return registry
