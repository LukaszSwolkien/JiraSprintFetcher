#!/usr/bin/env python3
"""
Jira Sprint Issues Tracker

This script retrieves issues from the active sprint for specified engineers,
showing issues that are either not done or recently updated.
"""

import argparse
import sys
import yaml
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

# Configure logging (disabled by default, only errors shown)
logging.basicConfig(level=logging.ERROR, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class JiraAPIError(Exception):
    """Custom exception for Jira API errors"""
    pass


class JiraSprintTracker:
    """Main class for tracking Jira sprint issues"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the Jira client with configuration"""
        self.base_url = config['jira_base_url'].rstrip('/')
        self.project_key = config['project_key']
        self.board_id = config['board_id']
        self.recent_days = config['recent_days']
        self.engineers = config['engineers']
        
        # Setup authentication
        self.auth = HTTPBasicAuth(
            config['email'],
            config['api_token']
        )
        
        # Setup session for connection pooling
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        # Calculate cutoff date for recent updates
        self.cutoff_date = datetime.now() - timedelta(days=self.recent_days)
        
    def _make_request(self, endpoint: str, params: Optional[Dict] = None, api_version: str = "api/3") -> Dict:
        """Make a request to the Jira API with error handling"""
        url = f"{self.base_url}/rest/{api_version}/{endpoint}"
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            raise JiraAPIError(f"Request timeout for {endpoint}")
        except requests.exceptions.ConnectionError:
            raise JiraAPIError(f"Connection error for {endpoint}")
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                raise JiraAPIError("Authentication failed. Check your email and API token.")
            elif response.status_code == 403:
                raise JiraAPIError("Access denied. Check your permissions.")
            elif response.status_code == 404:
                raise JiraAPIError(f"Resource not found: {endpoint}")
            else:
                raise JiraAPIError(f"HTTP {response.status_code}: {response.text}")
        except requests.exceptions.RequestException as e:
            raise JiraAPIError(f"Request failed: {str(e)}")
    
    def get_active_sprint(self) -> Optional[Dict]:
        """Get the currently active sprint for the board"""
        try:
            endpoint = f"board/{self.board_id}/sprint"
            params = {'state': 'active'}
            
            data = self._make_request(endpoint, params, api_version="agile/1.0")
            
            if not data.get('values'):
                return None
                
            # Return the first active sprint (there should typically be only one)
            return data['values'][0]
            
        except JiraAPIError:
            raise
        except Exception as e:
            raise JiraAPIError(f"Error getting active sprint: {str(e)}")
    
    def search_issues_for_engineer(self, engineer: str, sprint_id: int) -> List[Dict]:
        """Search for issues assigned to an engineer in the active sprint"""
        try:
            # Build JQL query
            # Include issues that are either:
            # 1. Not in Done/Closed/Released status, OR
            # 2. Updated within the last N days
            cutoff_str = self.cutoff_date.strftime('%Y-%m-%d')
            
            jql = (
                f'project = "{self.project_key}" AND '
                f'sprint = {sprint_id} AND '
                f'assignee in ("{engineer}") AND '
                f'(status NOT IN ("Done", "Closed", "Released") OR updated >= "{cutoff_str}")'
            )
            
            params = {
                'jql': jql,
                'fields': 'key,summary,status,updated,assignee',
                'maxResults': 100  # Adjust if needed
            }
            
            data = self._make_request('search', params, api_version="api/3")
            return data.get('issues', [])
            
        except JiraAPIError:
            raise
        except Exception as e:
            raise JiraAPIError(f"Error searching issues for {engineer}: {str(e)}")
    
    def get_issue_url(self, issue_key: str) -> str:
        """Generate the URL for a Jira issue"""
        return f"{self.base_url}/browse/{issue_key}"
    
    def run(self):
        """Main execution method"""
        try:
            # Get active sprint
            active_sprint = self.get_active_sprint()
            
            if not active_sprint:
                print("No active sprint found.")
                return
            
            sprint_name = active_sprint['name']
            sprint_id = active_sprint['id']
            
            print(f"{sprint_name}")
            print()
            
            # Process each engineer
            for engineer in self.engineers:
                try:
                    issues = self.search_issues_for_engineer(engineer, sprint_id)
                    
                    # Get engineer display name from the first issue (if any)
                    engineer_display_name = engineer
                    if issues:
                        # Try to get display name from assignee info
                        first_issue = issues[0]
                        if first_issue.get('fields', {}).get('assignee'):
                            assignee = first_issue['fields']['assignee']
                            engineer_display_name = assignee.get('displayName', engineer)
                    
                    print(engineer_display_name)
                    
                    if not issues:
                        print("  No matching issues found.")
                    else:
                        for issue in issues:
                            issue_key = issue['key']
                            issue_url = self.get_issue_url(issue_key)
                            print(f"  {issue_url}")
                    
                    print()  # Empty line between engineers
                    
                except JiraAPIError as e:
                    logger.error(f"Error processing {engineer}: {e}")
                    print(f"{engineer}")
                    print(f"  Error: {e}")
                    print()
                    
        except JiraAPIError as e:
            logger.error(f"Fatal error: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            sys.exit(1)


def load_config(config_file: str) -> Dict[str, Any]:
    """Load and validate configuration from YAML file"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Validate required fields
        required_fields = [
            'jira_base_url', 'email', 'api_token', 'project_key',
            'board_id', 'recent_days', 'engineers'
        ]
        
        missing_fields = []
        for field in required_fields:
            if field not in config:
                missing_fields.append(field)
        
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")
        
        # Validate data types
        if not isinstance(config['board_id'], int):
            raise ValueError("board_id must be an integer")
        
        if not isinstance(config['recent_days'], int) or config['recent_days'] < 0:
            raise ValueError("recent_days must be a non-negative integer")
        
        if not isinstance(config['engineers'], list) or not config['engineers']:
            raise ValueError("engineers must be a non-empty list")
        
        return config
        
    except FileNotFoundError:
        raise ValueError(f"Configuration file not found: {config_file}")
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML configuration: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error loading configuration: {str(e)}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Track Jira sprint issues for specified engineers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Configuration file should be a YAML file with the following structure:

jira_base_url: "https://your-domain.atlassian.net"
email: "your-email@example.com"
api_token: "your-api-token"
project_key: "PROJ"
board_id: 123
recent_days: 7
engineers:
  - "engineer1@example.com"
  - "engineer2@example.com"
        """
    )
    
    parser.add_argument(
        'config_file',
        help='Path to the YAML configuration file'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Load configuration
        config = load_config(args.config_file)
        
        # Create and run tracker
        tracker = JiraSprintTracker(config)
        tracker.run()
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)


if __name__ == '__main__':
    main()