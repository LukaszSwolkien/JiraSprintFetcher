import argparse
import requests
import yaml
import sys
from datetime import datetime, timedelta
from requests.auth import HTTPBasicAuth

def load_config(path):
    try:
        with open(path, 'r') as file:
            config = yaml.safe_load(file)
        required = ['jira_base_url', 'email', 'api_token', 'project_key', 'board_id', 'recent_days', 'engineers']
        for key in required:
            if key not in config:
                raise KeyError(f"Missing required configuration key: '{key}'")
        return config
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)

def jira_api_get(url, auth, params=None):
    headers = {'Accept': 'application/json'}
    try:
        response = requests.get(url, headers=headers, auth=auth, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error calling Jira API: {e} (URL: {url})")
        sys.exit(2)

def get_active_sprint(jira_base_url, board_id, auth):
    url = f"{jira_base_url}/rest/agile/1.0/board/{board_id}/sprint"
    data = jira_api_get(url, auth, params={"state": "active"})
    sprints = data.get("values", [])
    if not sprints:
        print("No active sprints found for the specified board.")
        sys.exit(3)
    return sprints[0]  # Assume only one active sprint per board

def get_user_display_map(jira_base_url, engineers, auth):
    # Map names/emails to display names using Jira's user search API
    display_map = {}
    for identifier in engineers:
        url = f"{jira_base_url}/rest/api/3/user/search"
        # Try email, then display name
        params = {"query": identifier, "maxResults": 2}
        data = jira_api_get(url, auth, params=params)
        if data:
            display_map[identifier] = (data[0]['displayName'], data[0]['accountId'])
        else:
            print(f"Warning: Engineer '{identifier}' not found in Jira.")
    return display_map

def search_issues(jira_base_url, project_key, sprint_id, account_id, recent_days, auth):
    # Build JQL
    n_days_ago = (datetime.now() - timedelta(days=recent_days)).strftime('%Y-%m-%d')
    jql = (
        f'project = "{project_key}" AND '
        f'assignee = "{account_id}" AND '
        f'sprint = {sprint_id} AND '
        '('
        'statusCategory != Done '
        f'OR updated >= "{n_days_ago}"'
        ')'
    )
    url = f"{jira_base_url}/rest/api/3/search"
    params = {
        "jql": jql,
        "fields": "key",
        "maxResults": 100
    }
    data = jira_api_get(url, auth, params=params)
    issues = data.get("issues", [])
    issue_urls = [f"{jira_base_url}/browse/{issue['key']}" for issue in issues]
    return issue_urls

def main():
    parser = argparse.ArgumentParser(description="Jira Sprint Issue Fetcher")
    parser.add_argument("config", help="Path to YAML configuration file")
    args = parser.parse_args()

    config = load_config(args.config)
    auth = HTTPBasicAuth(config['email'], config['api_token'])

    # Step 1: Get active sprint
    sprint = get_active_sprint(config['jira_base_url'], config['board_id'], auth)
    sprint_id = sprint['id']
    sprint_name = sprint['name']
    print(f"Active Sprint: {sprint_name}\n")

    # Step 2: Map engineers to display names and account IDs
    display_map = get_user_display_map(config['jira_base_url'], config['engineers'], auth)

    # Step 3: For each engineer, search for relevant issues
    for original, (display_name, account_id) in display_map.items():
        print(f"{display_name}:")
        issue_urls = search_issues(
            config['jira_base_url'],
            config['project_key'],
            sprint_id,
            account_id,
            config['recent_days'],
            auth
        )
        if not issue_urls:
            print("  (No matching issues)")
        else:
            for url in issue_urls:
                print(f"  {url}")
        print()  # Blank line between engineers

if __name__ == "__main__":
    main()