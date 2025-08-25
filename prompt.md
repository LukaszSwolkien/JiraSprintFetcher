Please write a Python script that interacts with a Jira Cloud instance using its REST API and HTTP Basic Authentication. The script should fulfill the following requirements:

Authentication:
Authenticate with the Jira instance using an email and an API token, both obtained from the configuration file.

Configuration:
The script must read all necessary parameters from a YAML configuration file, which will be provided as a command-line argument.
Required parameters include: the Jira base URL, a project key, a board ID, the number of days to consider for recently updated issues (N), and a list of engineer names or emails to query.

Issue Search:
Retrieve the currently active sprint for the specified board. For each engineer listed in the configuration, search for issues within the active sprint that are assigned to them and meet either of the following conditions:
The issue's status is not 'Done', 'Closed', or 'Released'
OR the issue was updated within the last N days (as specified in the configuration).

Output Format:
First, print the name of the active sprint.
Then, for each engineer, display their name (display name only, nothing else) followed by a list of the URLs for their matching issues.

Error Handling & Best Practices:
Implement error handling to gracefully manage API failures or invalid configurations, providing informative messages to the user.
Ensure that no deprecated Jira API functions or Python libraries are used.