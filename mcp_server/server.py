from mcp.server.fastmcp import FastMCP
from .tools import (
    obtener_stock_critico,
    obtener_ventas_por_periodo,
    obtener_top_productos,
    obtener_ingresos,
    obtener_resumen_negocio,
)

mcp = FastMCP("stockia")

mcp.tool()(obtener_stock_critico)
mcp.tool()(obtener_ventas_por_periodo)
mcp.tool()(obtener_top_productos)
mcp.tool()(obtener_ingresos)
mcp.tool()(obtener_resumen_negocio)

if __name__ == "__main__":
    mcp.run()
