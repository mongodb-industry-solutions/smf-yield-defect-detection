# --- Prompt Generation Functions ---

def get_chain_of_thoughts_prompt(agent_profile: str, agent_rules: str, agent_instructions: str, agent_goals: str, query_reported: str, agent_motive: str,
                                 agent_kind_of_data: str, embedding_model_name: str, chat_completion_model_name: str) -> str:
    """
    Generate a prompt for the chain of thoughts reasoning.

    Args:
        agent_profile (str): Profile of the agent generating the chain of thoughts.
        agent_rules (str): Rules the agent follows in generating the chain of thoughts.
        agent_instructions (str): Instructions for the agent generating the chain of thoughts.
        agent_goals (str): Goals of the agent generating the chain of thoughts.
        query_reported (str): Query reported to the agent.
        agent_motive (str): Motive of the agent generating the chain of thoughts.
        agent_kind_of_data (str): Kind of data the agent consumes.
        embedding_model_name (str): Name of the embedding model used by the agent.
        chat_completion_model_name (str): Name of the chat completion model used by the agent

    Returns:
        str: The prompt for the chain of thoughts reasoning
    """

    return f"""
        Agent Profile: {agent_profile}
        Instructions: {agent_instructions}
        Rules: {agent_rules}
        Goals: {agent_goals}


        You are an AI agent designed to {agent_motive}. Given the query:
        {query_reported}
        
        Generate a detailed chain-of-thought reasoning that outlines the following steps:
        1. Consume {agent_kind_of_data}.
        2. Generate an embedding for the complaint using {embedding_model_name}
        3. Perform a vector search on past queries in MongoDB Atlas.
        4. Persist {agent_kind_of_data} into MongoDB.
        5. Use {chat_completion_model_name}'s ChatCompletion model to generate a final summary and recommendation.
        
        Please provide your chain-of-thought as a numbered list with explanations for each step.
        """


def get_llm_recommendation_prompt(agent_role: str, agent_kind_of_data: str, critical_info: str, timeseries_data: str, historical_recommendations_list: str) -> str:
    """
    Generate a prompt for the LLM recommendation.

    Args:
        agent_role (str): Role of the agent generating the LLM recommendation.
        agent_kind_of_data (str): Kind of data the agent consumes.
        critical_info (str): Critical information for the LLM recommendation.
        timeseries_data (str): Timeseries data for the LLM recommendation.
        historical_recommendations_list (str): List of historical recommendations for the LLM recommendation.

    Returns:
        str: The prompt for the LLM recommendation
    """

    return f"""
        You are a helpful {agent_role}. {critical_info} 
        
        Given the following {agent_kind_of_data} and past recommendations, please analyze the data and recommend an immediate action with a clear explanation.
        
        {agent_kind_of_data}: {timeseries_data}

        Past Recommendations: {historical_recommendations_list}
        """