import importlib
from langgraph.graph import StateGraph, END
from agent_state import AgentState
from config.config_loader import ConfigLoader


def resolve_tool(tool_path):
    """
    Dynamically import a tool function based on its import path.

    Args:
        tool_path (str): The full import path of the tool (e.g., "agent_tools.get_data_from_csv_tool").

    Returns:
        function: The imported tool function.
    """
    module_name, function_name = tool_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, function_name)


def create_workflow_graph(checkpointer=None):
    """
    Create the LangGraph StateGraph for the agent workflow based on the JSON config file.

    Args:
        checkpointer (AgentCheckpointer, optional): AgentCheckpointer instance. Default is None.

    Returns:
        StateGraph: LangGraph StateGraph for the agent workflow
    """
    # Load configuration
    config_loader = ConfigLoader()
    graph_config = config_loader.get("AGENT_WORKFLOW_GRAPH")

    graph = StateGraph(AgentState)

    # Add nodes
    for node in graph_config["nodes"]:
        tool_function = resolve_tool(node["tool"])
        graph.add_node(node["id"], tool_function)

    # Add edges
    for edge in graph_config["edges"]:
        from_node = edge["from"]
        to_node = edge["to"]
        if to_node == "END":
            graph.add_edge(from_node, END)
        else:
            graph.add_edge(from_node, to_node)

    # Set entry point
    graph.set_entry_point(graph_config["entry_point"])

    # Compile the graph
    if checkpointer:
        return graph.compile(checkpointer=checkpointer)
    else:
        return graph.compile()


if __name__ == "__main__":
    # Example usage
    workflow = create_workflow_graph()

    # Graph compilation and visualization
    graph = workflow.get_graph()

    # Print the graph in ASCII format
    ascii_graph = graph.draw_ascii()
    print(ascii_graph)