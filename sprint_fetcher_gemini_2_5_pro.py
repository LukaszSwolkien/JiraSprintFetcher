import argparse
import sys
import yaml
import requests
from requests.auth import HTTPBasicAuth

def load_config(file_path):
    """
    Loads and validates the YAML configuration file.

    Args:
        file_path (str): The path to the configuration file.

    Returns:
        dict: The loaded configuration dictionary.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If any required keys are missing from the config.
    """
    required_keys = [
        'email', 'api_token', 'jira_base_url', 'project_key', 
        'board_id', 'recent_days', 'engineers'
    ]
    try:
        with open(file_path, 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file not found at '{file_path}'")
        raise

    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise ValueError(f"Error: Missing required keys in configuration file: {', '.join(missing_keys)}")
    
    return config

def get_active_sprint(base_url, board_id, auth):
    """
    Retrieves the currently active sprint for a given board.

    Args:
        base_url (str): The base URL of the Jira instance.
        board_id (int): The ID of the Jira board.
        auth (HTTPBasicAuth): The authentication object.

    Returns:
        dict: A dictionary containing the active sprint's ID and name, or None if no active sprint is found.
    """
    url = f"{base_url}/rest/agile/1.0/board/{board_id}/sprint"
    params = {'state': 'active'}
    
    try:
        response = requests.get(url, params=params, auth=auth, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        sprints = response.json().get('values', [])
        if sprints:
            return sprints[0] # The API returns the active sprint first
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching active sprint: {e}")
        return None

def search_issues_for_engineer(base_url, sprint_id, engineer, recent_days, auth):
    """
    Searches for issues assigned to an engineer in the active sprint based on status or update time.

    Args:
        base_url (str): The base URL of the Jira instance.
        sprint_id (int): The ID of the active sprint.
        engineer (str): The name or email of the engineer to search for.
        recent_days (int): The number of days to look back for updated issues.
        auth (HTTPBasicAuth): The authentication object.

    Returns:
        list: A list of URLs for the matching issues.
    """
    # JQL to find issues in the sprint assigned to the engineer that are either not done OR were recently updated.
    jql_query = (
        f'sprint = {sprint_id} AND assignee = "{engineer}" AND '
        f'(status not in ("Done", "Closed", "Released") OR updated >= -{recent_days}d)'
    )
    
    url = f"{base_url}/rest/api/3/search"
    params = {'jql': jql_query}
    
    try:
        response = requests.get(url, params=params, auth=auth, timeout=10)
        response.raise_for_status()
        issues = response.json().get('issues', [])
        
        # Construct the full browsable URL for each issue
        issue_urls = [f"{base_url}/browse/{issue['key']}" for issue in issues]
        return issue_urls
    except requests.exceptions.RequestException as e:
        print(f"Error searching issues for {engineer}: {e}")
        return []

def main():
    """Main function to orchestrate the script execution."""
    parser = argparse.ArgumentParser(description="Query Jira for active sprint issues per engineer.")
    parser.add_argument("config_file", help="Path to the YAML configuration file.")
    args = parser.parse_args()

    try:
        config = load_config(args.config_file)
    except (FileNotFoundError, ValueError) as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    # Extract config values
    email = config['email']
    api_token = config['api_token']
    jira_base_url = config['jira_base_url'].rstrip('/')
    board_id = config['board_id']
    recent_days = config['recent_days']
    engineers = config['engineers']

    auth = HTTPBasicAuth(email, api_token)

    # 1. Get the active sprint
    active_sprint = get_active_sprint(jira_base_url, board_id, auth)
    if not active_sprint:
        print("Could not find an active sprint for the specified board.", file=sys.stderr)
        sys.exit(1)

    sprint_id = active_sprint['id']
    sprint_name = active_sprint['name']
    print(f"Active Sprint: {sprint_name}\n")

    # 2. Search for issues for each engineer
    for engineer in engineers:
        print(f"--- {engineer} ---")
        issues = search_issues_for_engineer(jira_base_url, sprint_id, engineer, recent_days, auth)
        
        if issues:
            for issue_url in issues:
                print(issue_url)
        else:
            print("No matching issues found.")
        print() # Add a blank line for readability

if __name__ == "__main__":
    main()