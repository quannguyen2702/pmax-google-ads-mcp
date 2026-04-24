from typing import Any, Dict, List, Optional, Union
from pydantic import Field
import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
import logging

# MCP
from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('google_ads_server')

mcp = FastMCP(
    "google-ads-server",
    dependencies=[
        "google-auth-oauthlib",
        "google-auth",
        "requests",
        "python-dotenv"
    ]
)

# Constants and configuration
SCOPES = ['https://www.googleapis.com/auth/adwords']
API_VERSION = "v21"  # Google Ads API version

# Load environment variables
try:
    from dotenv import load_dotenv
    # Load from .env file if it exists
    load_dotenv()
    logger.info("Environment variables loaded from .env file")
except ImportError:
    logger.warning("python-dotenv not installed, skipping .env file loading")

# Get credentials from environment variables
GOOGLE_ADS_CREDENTIALS_PATH = os.environ.get("GOOGLE_ADS_CREDENTIALS_PATH")
GOOGLE_ADS_DEVELOPER_TOKEN = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN")
GOOGLE_ADS_LOGIN_CUSTOMER_ID = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")
GOOGLE_ADS_AUTH_TYPE = os.environ.get("GOOGLE_ADS_AUTH_TYPE", "oauth")  # oauth or service_account

def format_customer_id(customer_id: str) -> str:
    """Format customer ID to ensure it's 10 digits without dashes."""
    customer_id = str(customer_id)
    customer_id = customer_id.replace('\"', '').replace('"', '')
    customer_id = ''.join(char for char in customer_id if char.isdigit())
    return customer_id.zfill(10)

def get_credentials():
    """Get and refresh OAuth credentials or service account credentials based on the auth type."""
    if not GOOGLE_ADS_CREDENTIALS_PATH:
        raise ValueError("GOOGLE_ADS_CREDENTIALS_PATH environment variable not set")
    
    auth_type = GOOGLE_ADS_AUTH_TYPE.lower()
    logger.info(f"Using authentication type: {auth_type}")
    
    if auth_type == "service_account":
        try:
            return get_service_account_credentials()
        except Exception as e:
            logger.error(f"Error with service account authentication: {str(e)}")
            raise
    
    return get_oauth_credentials()

def get_service_account_credentials():
    """Get credentials using a service account key file."""
    logger.info(f"Loading service account credentials from {GOOGLE_ADS_CREDENTIALS_PATH}")
    
    if not os.path.exists(GOOGLE_ADS_CREDENTIALS_PATH):
        raise FileNotFoundError(f"Service account key file not found at {GOOGLE_ADS_CREDENTIALS_PATH}")
    
    try:
        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_ADS_CREDENTIALS_PATH, 
            scopes=SCOPES
        )
        
        impersonation_email = os.environ.get("GOOGLE_ADS_IMPERSONATION_EMAIL")
        if impersonation_email:
            logger.info(f"Impersonating user: {impersonation_email}")
            credentials = credentials.with_subject(impersonation_email)
            
        return credentials
        
    except Exception as e:
        logger.error(f"Error loading service account credentials: {str(e)}")
        raise

def get_oauth_credentials():
    """Get and refresh OAuth user credentials."""
    creds = None
    client_config = None
    
    token_path = GOOGLE_ADS_CREDENTIALS_PATH
    if os.path.exists(token_path) and not os.path.basename(token_path).endswith('.json'):
        token_dir = os.path.dirname(token_path)
        token_path = os.path.join(token_dir, 'google_ads_token.json')
    
    if os.path.exists(token_path):
        try:
            logger.info(f"Loading OAuth credentials from {token_path}")
            with open(token_path, 'r') as f:
                creds_data = json.load(f)
                if "installed" in creds_data or "web" in creds_data:
                    client_config = creds_data
                    logger.info("Found OAuth client configuration")
                else:
                    logger.info("Found existing OAuth token")
                    creds = Credentials.from_authorized_user_info(creds_data, SCOPES)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in token file: {token_path}")
            creds = None
        except Exception as e:
            logger.warning(f"Error loading credentials: {str(e)}")
            creds = None
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                logger.info("Refreshing expired token")
                creds.refresh(Request())
                logger.info("Token successfully refreshed")
            except RefreshError as e:
                logger.warning(f"Error refreshing token: {str(e)}, will try to get new token")
                creds = None
            except Exception as e:
                logger.error(f"Unexpected error refreshing token: {str(e)}")
                raise
        
        if not creds:
            if not client_config:
                logger.info("Creating OAuth client config from environment variables")
                client_id = os.environ.get("GOOGLE_ADS_CLIENT_ID")
                client_secret = os.environ.get("GOOGLE_ADS_CLIENT_SECRET")
                
                if not client_id or not client_secret:
                    raise ValueError("GOOGLE_ADS_CLIENT_ID and GOOGLE_ADS_CLIENT_SECRET must be set if no client config file exists")
                
                client_config = {
                    "installed": {
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
                    }
                }
            
            logger.info("Starting OAuth authentication flow")
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)
            logger.info("OAuth flow completed successfully")
        
        try:
            logger.info(f"Saving credentials to {token_path}")
            os.makedirs(os.path.dirname(token_path), exist_ok=True)
            with open(token_path, 'w') as f:
                f.write(creds.to_json())
        except Exception as e:
            logger.warning(f"Could not save credentials: {str(e)}")
    
    return creds

def get_headers(creds):
    """Get headers for Google Ads API requests."""
    if not GOOGLE_ADS_DEVELOPER_TOKEN:
        raise ValueError("GOOGLE_ADS_DEVELOPER_TOKEN environment variable not set")
    
    if isinstance(creds, service_account.Credentials):
        auth_req = Request()
        creds.refresh(auth_req)
        token = creds.token
    else:
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                try:
                    logger.info("Refreshing expired OAuth token in get_headers")
                    creds.refresh(Request())
                    logger.info("Token successfully refreshed in get_headers")
                except RefreshError as e:
                    logger.error(f"Error refreshing token in get_headers: {str(e)}")
                    raise ValueError(f"Failed to refresh OAuth token: {str(e)}")
                except Exception as e:
                    logger.error(f"Unexpected error refreshing token in get_headers: {str(e)}")
                    raise
            else:
                raise ValueError("OAuth credentials are invalid and cannot be refreshed")
        
        token = creds.token
        
    headers = {
        'Authorization': f'Bearer {token}',
        'developer-token': GOOGLE_ADS_DEVELOPER_TOKEN,
        'content-type': 'application/json'
    }
    
    if GOOGLE_ADS_LOGIN_CUSTOMER_ID:
        headers['login-customer-id'] = format_customer_id(GOOGLE_ADS_LOGIN_CUSTOMER_ID)
    
    return headers


def _resolve_date_range(days: int) -> str:
    """Map days to valid GAQL date range string."""
    mapping = {7: "LAST_7_DAYS", 14: "LAST_14_DAYS", 30: "LAST_30_DAYS", 90: "LAST_90_DAYS"}
    return mapping.get(days, "LAST_30_DAYS")


def _execute_raw_query(customer_id: str, query: str) -> dict:
    """Execute GAQL query and return raw JSON response. Raises on error."""
    creds = get_credentials()
    headers = get_headers(creds)
    formatted_customer_id = format_customer_id(customer_id)
    url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{formatted_customer_id}/googleAds:search"
    
    payload = {"query": query}
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        raise Exception(f"API Error: {response.text}")
    
    return response.json()


# ============================================================================
# EXISTING TOOLS (UNCHANGED)
# ============================================================================

@mcp.tool()
async def list_accounts() -> str:
    """
    Lists all accessible Google Ads accounts.
    
    This is typically the first command you should run to identify which accounts 
    you have access to. The returned account IDs can be used in subsequent commands.
    
    Returns:
        A formatted list of all Google Ads accounts accessible with your credentials
    """
    try:
        creds = get_credentials()
        headers = get_headers(creds)
        
        url = f"https://googleads.googleapis.com/{API_VERSION}/customers:listAccessibleCustomers"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return f"Error accessing accounts: {response.text}"
        
        customers = response.json()
        if not customers.get('resourceNames'):
            return "No accessible accounts found."
        
        result_lines = ["Accessible Google Ads Accounts:"]
        result_lines.append("-" * 50)
        
        for resource_name in customers['resourceNames']:
            customer_id = resource_name.split('/')[-1]
            formatted_id = format_customer_id(customer_id)
            result_lines.append(f"Account ID: {formatted_id}")
        
        return "\n".join(result_lines)
    
    except Exception as e:
        return f"Error listing accounts: {str(e)}"

@mcp.tool()
async def execute_gaql_query(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes). Example: '9873186703'"),
    query: str = Field(description="Valid GAQL query string following Google Ads Query Language syntax")
) -> str:
    """
    Execute a custom GAQL (Google Ads Query Language) query.
    
    Args:
        customer_id: The Google Ads customer ID as a string (10 digits, no dashes)
        query: The GAQL query to execute (must follow GAQL syntax)
        
    Returns:
        Formatted query results or error message
    """
    try:
        creds = get_credentials()
        headers = get_headers(creds)
        
        formatted_customer_id = format_customer_id(customer_id)
        url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{formatted_customer_id}/googleAds:search"
        
        payload = {"query": query}
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            return f"Error executing query: {response.text}"
        
        results = response.json()
        if not results.get('results'):
            return "No results found for the query."
        
        result_lines = [f"Query Results for Account {formatted_customer_id}:"]
        result_lines.append("-" * 80)
        
        fields = []
        first_result = results['results'][0]
        for key in first_result:
            if isinstance(first_result[key], dict):
                for subkey in first_result[key]:
                    fields.append(f"{key}.{subkey}")
            else:
                fields.append(key)
        
        result_lines.append(" | ".join(fields))
        result_lines.append("-" * 80)
        
        for result in results['results']:
            row_data = []
            for field in fields:
                if "." in field:
                    parent, child = field.split(".")
                    value = str(result.get(parent, {}).get(child, ""))
                else:
                    value = str(result.get(field, ""))
                row_data.append(value)
            result_lines.append(" | ".join(row_data))
        
        return "\n".join(result_lines)
    
    except Exception as e:
        return f"Error executing GAQL query: {str(e)}"

@mcp.tool()
async def get_campaign_performance(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes). Example: '9873186703'"),
    days: int = Field(default=30, description="Number of days to look back (7, 30, 90, etc.)")
) -> str:
    """
    Get campaign performance metrics for the specified time period.
    
    RECOMMENDED WORKFLOW:
    1. First run list_accounts() to get available account IDs
    2. Then run get_account_currency() to see what currency the account uses
    3. Finally run this command to get campaign performance
    
    Note: Cost values are in micros (millionths) of the account currency
    """
    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.average_cpc
        FROM campaign
        WHERE segments.date DURING LAST_{days}_DAYS
        ORDER BY metrics.cost_micros DESC
        LIMIT 50
    """
    
    return await execute_gaql_query(customer_id, query)

@mcp.tool()
async def get_ad_performance(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes). Example: '9873186703'"),
    days: int = Field(default=30, description="Number of days to look back (7, 30, 90, etc.)")
) -> str:
    """
    Get ad performance metrics for the specified time period.
    
    Note: Cost values are in micros (millionths) of the account currency
    """
    query = f"""
        SELECT
            ad_group_ad.ad.id,
            ad_group_ad.ad.name,
            ad_group_ad.status,
            campaign.name,
            ad_group.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions
        FROM ad_group_ad
        WHERE segments.date DURING LAST_{days}_DAYS
        ORDER BY metrics.impressions DESC
        LIMIT 50
    """
    
    return await execute_gaql_query(customer_id, query)

@mcp.tool()
async def run_gaql(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes). Example: '9873186703'"),
    query: str = Field(description="Valid GAQL query string following Google Ads Query Language syntax"),
    format: str = Field(default="table", description="Output format: 'table', 'json', or 'csv'")
) -> str:
    """
    Execute any arbitrary GAQL query with custom formatting options.
    
    This is the most powerful tool for custom Google Ads data queries.
    Supports 'table', 'json', and 'csv' output formats.
    
    Note: Cost values are in micros (millionths) of the account currency
    """
    try:
        creds = get_credentials()
        headers = get_headers(creds)
        
        formatted_customer_id = format_customer_id(customer_id)
        url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{formatted_customer_id}/googleAds:search"
        
        payload = {"query": query}
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            return f"Error executing query: {response.text}"
        
        results = response.json()
        if not results.get('results'):
            return "No results found for the query."
        
        if format.lower() == "json":
            return json.dumps(results, indent=2)
        
        elif format.lower() == "csv":
            fields = []
            first_result = results['results'][0]
            for key, value in first_result.items():
                if isinstance(value, dict):
                    for subkey in value:
                        fields.append(f"{key}.{subkey}")
                else:
                    fields.append(key)
            
            csv_lines = [",".join(fields)]
            for result in results['results']:
                row_data = []
                for field in fields:
                    if "." in field:
                        parent, child = field.split(".")
                        value = str(result.get(parent, {}).get(child, "")).replace(",", ";")
                    else:
                        value = str(result.get(field, "")).replace(",", ";")
                    row_data.append(value)
                csv_lines.append(",".join(row_data))
            
            return "\n".join(csv_lines)
        
        else:  # default table format
            result_lines = [f"Query Results for Account {formatted_customer_id}:"]
            result_lines.append("-" * 100)
            
            fields = []
            field_widths = {}
            first_result = results['results'][0]
            
            for key, value in first_result.items():
                if isinstance(value, dict):
                    for subkey in value:
                        field = f"{key}.{subkey}"
                        fields.append(field)
                        field_widths[field] = len(field)
                else:
                    fields.append(key)
                    field_widths[key] = len(key)
            
            for result in results['results']:
                for field in fields:
                    if "." in field:
                        parent, child = field.split(".")
                        value = str(result.get(parent, {}).get(child, ""))
                    else:
                        value = str(result.get(field, ""))
                    field_widths[field] = max(field_widths[field], len(value))
            
            header = " | ".join(f"{field:{field_widths[field]}}" for field in fields)
            result_lines.append(header)
            result_lines.append("-" * len(header))
            
            for result in results['results']:
                row_data = []
                for field in fields:
                    if "." in field:
                        parent, child = field.split(".")
                        value = str(result.get(parent, {}).get(child, ""))
                    else:
                        value = str(result.get(field, ""))
                    row_data.append(f"{value:{field_widths[field]}}")
                result_lines.append(" | ".join(row_data))
            
            return "\n".join(result_lines)
    
    except Exception as e:
        return f"Error executing GAQL query: {str(e)}"

@mcp.tool()
async def get_ad_creatives(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes). Example: '9873186703'")
) -> str:
    """
    Get ad creative details including headlines, descriptions, and URLs.
    Great for creative audits.
    """
    query = """
        SELECT
            ad_group_ad.ad.id,
            ad_group_ad.ad.name,
            ad_group_ad.ad.type,
            ad_group_ad.ad.final_urls,
            ad_group_ad.status,
            ad_group_ad.ad.responsive_search_ad.headlines,
            ad_group_ad.ad.responsive_search_ad.descriptions,
            ad_group.name,
            campaign.name
        FROM ad_group_ad
        WHERE ad_group_ad.status != 'REMOVED'
        ORDER BY campaign.name, ad_group.name
        LIMIT 50
    """
    
    try:
        creds = get_credentials()
        headers = get_headers(creds)
        
        formatted_customer_id = format_customer_id(customer_id)
        url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{formatted_customer_id}/googleAds:search"
        
        payload = {"query": query}
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            return f"Error retrieving ad creatives: {response.text}"
        
        results = response.json()
        if not results.get('results'):
            return "No ad creatives found for this customer ID."
        
        output_lines = [f"Ad Creatives for Customer ID {formatted_customer_id}:"]
        output_lines.append("=" * 80)
        
        for i, result in enumerate(results['results'], 1):
            ad = result.get('adGroupAd', {}).get('ad', {})
            ad_group = result.get('adGroup', {})
            campaign = result.get('campaign', {})
            
            output_lines.append(f"\n{i}. Campaign: {campaign.get('name', 'N/A')}")
            output_lines.append(f"   Ad Group: {ad_group.get('name', 'N/A')}")
            output_lines.append(f"   Ad ID: {ad.get('id', 'N/A')}")
            output_lines.append(f"   Ad Name: {ad.get('name', 'N/A')}")
            output_lines.append(f"   Status: {result.get('adGroupAd', {}).get('status', 'N/A')}")
            output_lines.append(f"   Type: {ad.get('type', 'N/A')}")
            
            rsa = ad.get('responsiveSearchAd', {})
            if rsa:
                if 'headlines' in rsa:
                    output_lines.append("   Headlines:")
                    for headline in rsa['headlines']:
                        output_lines.append(f"     - {headline.get('text', 'N/A')}")
                
                if 'descriptions' in rsa:
                    output_lines.append("   Descriptions:")
                    for desc in rsa['descriptions']:
                        output_lines.append(f"     - {desc.get('text', 'N/A')}")
            
            final_urls = ad.get('finalUrls', [])
            if final_urls:
                output_lines.append(f"   Final URLs: {', '.join(final_urls)}")
            
            output_lines.append("-" * 80)
        
        return "\n".join(output_lines)
    
    except Exception as e:
        return f"Error retrieving ad creatives: {str(e)}"

@mcp.tool()
async def get_account_currency(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes). Example: '9873186703'")
) -> str:
    """
    Retrieve the default currency code used by the Google Ads account.
    
    IMPORTANT: Run this first before analyzing cost data to understand which currency
    the account uses.
    """
    query = """
        SELECT
            customer.id,
            customer.currency_code
        FROM customer
        LIMIT 1
    """
    
    try:
        creds = get_credentials()
        
        if not creds.valid:
            logger.info("Credentials not valid, attempting refresh...")
            if hasattr(creds, 'refresh_token') and creds.refresh_token:
                creds.refresh(Request())
                logger.info("Credentials refreshed successfully")
            else:
                raise ValueError("Invalid credentials and no refresh token available")
        
        headers = get_headers(creds)
        
        formatted_customer_id = format_customer_id(customer_id)
        url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{formatted_customer_id}/googleAds:search"
        
        payload = {"query": query}
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            return f"Error retrieving account currency: {response.text}"
        
        results = response.json()
        if not results.get('results'):
            return "No account information found for this customer ID."
        
        customer = results['results'][0].get('customer', {})
        currency_code = customer.get('currencyCode', 'Not specified')
        
        return f"Account {formatted_customer_id} uses currency: {currency_code}"
    
    except Exception as e:
        logger.error(f"Error retrieving account currency: {str(e)}")
        return f"Error retrieving account currency: {str(e)}"

@mcp.tool()
async def get_image_assets(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes). Example: '9873186703'"),
    limit: int = Field(default=50, description="Maximum number of image assets to return")
) -> str:
    """
    Retrieve all image assets in the account including their full-size URLs.
    """
    query = f"""
        SELECT
            asset.id,
            asset.name,
            asset.type,
            asset.image_asset.full_size.url,
            asset.image_asset.full_size.height_pixels,
            asset.image_asset.full_size.width_pixels,
            asset.image_asset.file_size
        FROM
            asset
        WHERE
            asset.type = 'IMAGE'
        LIMIT {limit}
    """
    
    try:
        creds = get_credentials()
        headers = get_headers(creds)
        
        formatted_customer_id = format_customer_id(customer_id)
        url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{formatted_customer_id}/googleAds:search"
        
        payload = {"query": query}
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            return f"Error retrieving image assets: {response.text}"
        
        results = response.json()
        if not results.get('results'):
            return "No image assets found for this customer ID."
        
        output_lines = [f"Image Assets for Customer ID {formatted_customer_id}:"]
        output_lines.append("=" * 80)
        
        for i, result in enumerate(results['results'], 1):
            asset = result.get('asset', {})
            image_asset = asset.get('imageAsset', {})
            full_size = image_asset.get('fullSize', {})
            
            output_lines.append(f"\n{i}. Asset ID: {asset.get('id', 'N/A')}")
            output_lines.append(f"   Name: {asset.get('name', 'N/A')}")
            
            if full_size:
                output_lines.append(f"   Image URL: {full_size.get('url', 'N/A')}")
                output_lines.append(f"   Dimensions: {full_size.get('widthPixels', 'N/A')} x {full_size.get('heightPixels', 'N/A')} px")
            
            file_size = image_asset.get('fileSize', 'N/A')
            if file_size != 'N/A':
                file_size_kb = int(file_size) / 1024
                output_lines.append(f"   File Size: {file_size_kb:.2f} KB")
            
            output_lines.append("-" * 80)
        
        return "\n".join(output_lines)
    
    except Exception as e:
        return f"Error retrieving image assets: {str(e)}"

@mcp.tool()
async def download_image_asset(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes). Example: '9873186703'"),
    asset_id: str = Field(description="The ID of the image asset to download"),
    output_dir: str = Field(default="./ad_images", description="Directory to save the downloaded image")
) -> str:
    """
    Download a specific image asset from a Google Ads account.
    """
    query = f"""
        SELECT
            asset.id,
            asset.name,
            asset.image_asset.full_size.url
        FROM
            asset
        WHERE
            asset.type = 'IMAGE'
            AND asset.id = {asset_id}
        LIMIT 1
    """
    
    try:
        creds = get_credentials()
        headers = get_headers(creds)
        
        formatted_customer_id = format_customer_id(customer_id)
        url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{formatted_customer_id}/googleAds:search"
        
        payload = {"query": query}
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            return f"Error retrieving image asset: {response.text}"
        
        results = response.json()
        if not results.get('results'):
            return f"No image asset found with ID {asset_id}"
        
        asset = results['results'][0].get('asset', {})
        image_url = asset.get('imageAsset', {}).get('fullSize', {}).get('url')
        asset_name = asset.get('name', f"image_{asset_id}")
        
        if not image_url:
            return f"No download URL found for image asset ID {asset_id}"
        
        try:
            base_dir = Path.cwd()
            resolved_output_dir = Path(output_dir).resolve()
            
            try:
                resolved_output_dir.relative_to(base_dir)
            except ValueError:
                resolved_output_dir = base_dir / "ad_images"
                logger.warning(f"Invalid output directory '{output_dir}' - using default './ad_images'")
            
            resolved_output_dir.mkdir(parents=True, exist_ok=True)
            
        except Exception as e:
            return f"Error creating output directory: {str(e)}"
        
        image_response = requests.get(image_url)
        if image_response.status_code != 200:
            return f"Failed to download image: HTTP {image_response.status_code}"
        
        safe_name = ''.join(c for c in asset_name if c.isalnum() or c in ' ._-')
        filename = f"{asset_id}_{safe_name}.jpg"
        file_path = resolved_output_dir / filename
        
        with open(file_path, 'wb') as f:
            f.write(image_response.content)
        
        return f"Successfully downloaded image asset {asset_id} to {file_path}"
    
    except Exception as e:
        return f"Error downloading image asset: {str(e)}"

@mcp.tool()
async def get_asset_usage(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes). Example: '9873186703'"),
    asset_id: str = Field(default=None, description="Optional: specific asset ID to look up"),
    asset_type: str = Field(default="IMAGE", description="Asset type: 'IMAGE', 'TEXT', 'VIDEO', etc.")
) -> str:
    """
    Find where specific assets are being used in campaigns, ad groups, and ads.
    """
    where_clause = f"asset.type = '{asset_type}'"
    if asset_id:
        where_clause += f" AND asset.id = {asset_id}"
    
    assets_query = f"""
        SELECT asset.id, asset.name, asset.type
        FROM asset
        WHERE {where_clause}
        LIMIT 100
    """
    
    associations_query = f"""
        SELECT campaign.id, campaign.name, asset.id, asset.name, asset.type
        FROM campaign_asset
        WHERE {where_clause}
        LIMIT 500
    """
    
    try:
        creds = get_credentials()
        headers = get_headers(creds)
        
        formatted_customer_id = format_customer_id(customer_id)
        url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{formatted_customer_id}/googleAds:search"
        
        payload = {"query": assets_query}
        assets_response = requests.post(url, headers=headers, json=payload)
        
        if assets_response.status_code != 200:
            return f"Error retrieving assets: {assets_response.text}"
        
        assets_results = assets_response.json()
        if not assets_results.get('results'):
            return f"No {asset_type} assets found for this customer ID."
        
        payload = {"query": associations_query}
        assoc_response = requests.post(url, headers=headers, json=payload)
        
        if assoc_response.status_code != 200:
            return f"Error retrieving asset associations: {assoc_response.text}"
        
        assoc_results = assoc_response.json()
        
        output_lines = [f"Asset Usage for Customer ID {formatted_customer_id}:"]
        output_lines.append("=" * 80)
        
        asset_usage = {}
        
        for result in assets_results.get('results', []):
            asset = result.get('asset', {})
            a_id = asset.get('id')
            if a_id:
                asset_usage[a_id] = {
                    'name': asset.get('name', 'Unnamed asset'),
                    'type': asset.get('type', 'Unknown'),
                    'usage': []
                }
        
        for result in assoc_results.get('results', []):
            asset = result.get('asset', {})
            a_id = asset.get('id')
            
            if a_id and a_id in asset_usage:
                campaign = result.get('campaign', {})
                usage_info = {
                    'campaign_id': campaign.get('id', 'N/A'),
                    'campaign_name': campaign.get('name', 'N/A'),
                }
                asset_usage[a_id]['usage'].append(usage_info)
        
        for a_id, info in asset_usage.items():
            output_lines.append(f"\nAsset ID: {a_id}")
            output_lines.append(f"Name: {info['name']}")
            output_lines.append(f"Type: {info['type']}")
            
            if info['usage']:
                output_lines.append("Used in:")
                for usage in info['usage']:
                    output_lines.append(f"  - {usage['campaign_name']} ({usage['campaign_id']})")
            
            output_lines.append("=" * 80)
        
        return "\n".join(output_lines)
    
    except Exception as e:
        return f"Error retrieving asset usage: {str(e)}"

@mcp.tool()
async def analyze_image_assets(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes). Example: '9873186703'"),
    days: int = Field(default=30, description="Number of days to look back (7, 30, 90, etc.)")
) -> str:
    """
    Analyze image assets with their performance metrics across campaigns.
    """
    date_range = _resolve_date_range(days)
        
    query = f"""
        SELECT
            asset.id,
            asset.name,
            asset.image_asset.full_size.url,
            asset.image_asset.full_size.width_pixels,
            asset.image_asset.full_size.height_pixels,
            campaign.name,
            metrics.impressions,
            metrics.clicks,
            metrics.conversions,
            metrics.cost_micros
        FROM campaign_asset
        WHERE asset.type = 'IMAGE'
            AND segments.date DURING {date_range}
        ORDER BY metrics.impressions DESC
        LIMIT 200
    """
    
    try:
        creds = get_credentials()
        headers = get_headers(creds)
        
        formatted_customer_id = format_customer_id(customer_id)
        url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{formatted_customer_id}/googleAds:search"
        
        payload = {"query": query}
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            return f"Error analyzing image assets: {response.text}"
        
        results = response.json()
        if not results.get('results'):
            return "No image asset performance data found."
        
        assets_data = {}
        for result in results.get('results', []):
            asset = result.get('asset', {})
            asset_id = asset.get('id')
            
            if asset_id not in assets_data:
                assets_data[asset_id] = {
                    'name': asset.get('name', f"Asset {asset_id}"),
                    'url': asset.get('imageAsset', {}).get('fullSize', {}).get('url', 'N/A'),
                    'dimensions': f"{asset.get('imageAsset', {}).get('fullSize', {}).get('widthPixels', 'N/A')} x {asset.get('imageAsset', {}).get('fullSize', {}).get('heightPixels', 'N/A')}",
                    'impressions': 0, 'clicks': 0, 'conversions': 0, 'cost_micros': 0,
                    'campaigns': set()
                }
            
            metrics = result.get('metrics', {})
            assets_data[asset_id]['impressions'] += int(metrics.get('impressions', 0))
            assets_data[asset_id]['clicks'] += int(metrics.get('clicks', 0))
            assets_data[asset_id]['conversions'] += float(metrics.get('conversions', 0))
            assets_data[asset_id]['cost_micros'] += int(metrics.get('costMicros', 0))
            
            campaign = result.get('campaign', {})
            if campaign.get('name'):
                assets_data[asset_id]['campaigns'].add(campaign.get('name'))
        
        output_lines = [f"Image Asset Performance for Account {formatted_customer_id} (Last {days} days):"]
        output_lines.append("=" * 100)
        
        sorted_assets = sorted(assets_data.items(), key=lambda x: x[1]['impressions'], reverse=True)
        
        for asset_id, data in sorted_assets:
            ctr = (data['clicks'] / data['impressions'] * 100) if data['impressions'] > 0 else 0
            
            output_lines.append(f"\nAsset ID: {asset_id}")
            output_lines.append(f"Name: {data['name']}")
            output_lines.append(f"Dimensions: {data['dimensions']}")
            output_lines.append(f"  Impressions: {data['impressions']:,} | Clicks: {data['clicks']:,} | CTR: {ctr:.2f}%")
            output_lines.append(f"  Conversions: {data['conversions']:.2f} | Cost (micros): {data['cost_micros']:,}")
            output_lines.append(f"  Used in: {', '.join(list(data['campaigns'])[:5])}")
            if data['url'] != 'N/A':
                output_lines.append(f"  Image URL: {data['url']}")
            output_lines.append("-" * 100)
        
        return "\n".join(output_lines)
    
    except Exception as e:
        return f"Error analyzing image assets: {str(e)}"

@mcp.tool()
async def list_resources(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes). Example: '9873186703'")
) -> str:
    """List valid resources that can be used in GAQL FROM clauses."""
    query = """
        SELECT
            google_ads_field.name,
            google_ads_field.category,
            google_ads_field.data_type
        FROM google_ads_field
        WHERE google_ads_field.category = 'RESOURCE'
        ORDER BY google_ads_field.name
    """
    return await run_gaql(customer_id, query)


# ============================================================================
# NEW TOOLS — ASSET PERFORMANCE & BEYOND
# ============================================================================

@mcp.tool()
async def get_asset_performance(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes). Example: '9873186703'"),
    days: int = Field(default=30, description="Number of days to look back (7, 14, 30, 90)"),
    asset_type: str = Field(default="ALL", description="Filter by asset type: 'HEADLINE', 'DESCRIPTION', 'IMAGE', 'VIDEO', 'ALL'"),
    campaign_name_contains: str = Field(default="", description="Optional: filter by campaign name (partial match)")
) -> str:
    """
    Get detailed performance metrics for individual ad assets (headlines, descriptions, images, videos).
    
    Unlike ad-level metrics, this breaks down performance PER ASSET — so you can see
    which specific headline or image is driving clicks/conversions.
    
    Metrics returned: Impressions, Clicks, CTR, CPC, Cost, Conversions, Cost/Conv, Performance Label.
    
    Note: Google Ads API uses protobuf serialization which omits zero-value fields.
    This tool explicitly handles missing metrics as 0 to avoid data gaps.
    
    Args:
        customer_id: Google Ads customer ID (10 digits, no dashes)
        days: Lookback period (7, 14, 30, 90)
        asset_type: Filter — HEADLINE, DESCRIPTION, IMAGE, VIDEO, or ALL
        campaign_name_contains: Optional campaign name filter (case-insensitive partial match)
    """
    date_range = _resolve_date_range(days)
    
    # Build asset type filter
    asset_type_filter = ""
    asset_type_upper = asset_type.upper()
    if asset_type_upper == "HEADLINE":
        asset_type_filter = "AND ad_group_ad_asset_view.field_type = 'HEADLINE'"
    elif asset_type_upper == "DESCRIPTION":
        asset_type_filter = "AND ad_group_ad_asset_view.field_type = 'DESCRIPTION'"
    elif asset_type_upper == "IMAGE":
        asset_type_filter = "AND ad_group_ad_asset_view.field_type IN ('MARKETING_IMAGE', 'SQUARE_MARKETING_IMAGE', 'LOGO', 'LANDSCAPE_LOGO')"
    elif asset_type_upper == "VIDEO":
        asset_type_filter = "AND ad_group_ad_asset_view.field_type = 'YOUTUBE_VIDEO'"
    
    campaign_filter = ""
    if campaign_name_contains:
        campaign_filter = f"AND campaign.name LIKE '%{campaign_name_contains}%'"
    
    query = f"""
        SELECT
            campaign.name,
            ad_group.name,
            ad_group_ad_asset_view.field_type,
            asset.text_asset.text,
            asset.name,
            asset.type,
            ad_group_ad_asset_view.performance_label,
            ad_group_ad_asset_view.enabled,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.all_conversions
        FROM ad_group_ad_asset_view
        WHERE segments.date DURING {date_range}
            {asset_type_filter}
            {campaign_filter}
        ORDER BY metrics.impressions DESC
        LIMIT 500
    """
    
    try:
        results = _execute_raw_query(customer_id, query)
        
        if not results.get('results'):
            return f"No asset performance data found (days={days}, type={asset_type})."
        
        formatted_customer_id = format_customer_id(customer_id)
        output_lines = [f"Asset Performance for Account {formatted_customer_id} | Last {days} days | Type: {asset_type}"]
        output_lines.append("=" * 120)
        
        # Aggregate by asset text (same headline can appear in multiple ad groups)
        asset_agg = {}
        
        for result in results['results']:
            campaign = result.get('campaign', {})
            ad_group = result.get('adGroup', {})
            asset_view = result.get('adGroupAdAssetView', {})
            asset = result.get('asset', {})
            metrics = result.get('metrics', {})
            
            asset_text = asset.get('textAsset', {}).get('text', '') or asset.get('name', 'N/A')
            field_type = asset_view.get('fieldType', 'UNKNOWN')
            perf_label = asset_view.get('performanceLabel', 'UNRATED')
            enabled = asset_view.get('enabled', 'N/A')
            
            # CRITICAL: Handle protobuf zero-omission
            impressions = int(metrics.get('impressions', 0))
            clicks = int(metrics.get('clicks', 0))
            cost_micros = int(metrics.get('costMicros', 0))
            conversions = float(metrics.get('conversions', 0))
            all_conversions = float(metrics.get('allConversions', 0))
            
            agg_key = f"{asset_text}||{field_type}"
            
            if agg_key not in asset_agg:
                asset_agg[agg_key] = {
                    'text': asset_text, 'field_type': field_type,
                    'perf_label': perf_label, 'enabled': enabled,
                    'impressions': 0, 'clicks': 0, 'cost_micros': 0,
                    'conversions': 0, 'all_conversions': 0,
                    'campaigns': set(), 'ad_groups': set()
                }
            
            asset_agg[agg_key]['impressions'] += impressions
            asset_agg[agg_key]['clicks'] += clicks
            asset_agg[agg_key]['cost_micros'] += cost_micros
            asset_agg[agg_key]['conversions'] += conversions
            asset_agg[agg_key]['all_conversions'] += all_conversions
            asset_agg[agg_key]['campaigns'].add(campaign.get('name', 'N/A'))
            asset_agg[agg_key]['ad_groups'].add(ad_group.get('name', 'N/A'))
            
            label_priority = {'BEST': 4, 'GOOD': 3, 'LOW': 2, 'UNRATED': 1, 'UNKNOWN': 0}
            if label_priority.get(perf_label, 0) > label_priority.get(asset_agg[agg_key]['perf_label'], 0):
                asset_agg[agg_key]['perf_label'] = perf_label
        
        sorted_assets = sorted(asset_agg.values(), key=lambda x: x['impressions'], reverse=True)
        
        for i, data in enumerate(sorted_assets, 1):
            impressions = data['impressions']
            clicks = data['clicks']
            cost = data['cost_micros'] / 1_000_000
            conversions = data['conversions']
            
            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            cpc = (cost / clicks) if clicks > 0 else 0
            cost_per_conv = (cost / conversions) if conversions > 0 else 0
            
            output_lines.append(f"\n{i}. [{data['field_type']}] {data['text'][:80]}")
            output_lines.append(f"   Performance: {data['perf_label']} | Enabled: {data['enabled']}")
            output_lines.append(f"   Impressions: {impressions:>10,} | Clicks: {clicks:>8,} | CTR: {ctr:>6.2f}%")
            output_lines.append(f"   Cost: {cost:>12,.2f} | CPC: {cpc:>8,.2f} | Conversions: {conversions:>6.1f} | Cost/Conv: {cost_per_conv:>10,.2f}")
            output_lines.append(f"   Used in {len(data['campaigns'])} campaign(s): {', '.join(list(data['campaigns'])[:3])}")
        
        output_lines.append(f"\n{'=' * 120}")
        output_lines.append(f"Total assets: {len(sorted_assets)} | Data period: {date_range}")
        
        return "\n".join(output_lines)
    
    except Exception as e:
        return f"Error retrieving asset performance: {str(e)}"


@mcp.tool()
async def get_pmax_asset_groups(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes)"),
    days: int = Field(default=30, description="Number of days to look back (7, 14, 30, 90)"),
    campaign_name_contains: str = Field(default="", description="Optional: filter by PMax campaign name")
) -> str:
    """
    Get Performance Max asset group breakdown with performance metrics.
    
    Shows each asset group within PMax campaigns — impressions, clicks, conversions, cost —
    so you can identify which asset groups to scale or pause.
    
    Args:
        customer_id: Google Ads customer ID (10 digits)
        days: Lookback period (7, 14, 30, 90)
        campaign_name_contains: Optional campaign name filter
    """
    date_range = _resolve_date_range(days)
    
    campaign_filter = ""
    if campaign_name_contains:
        campaign_filter = f"AND campaign.name LIKE '%{campaign_name_contains}%'"
    
    query = f"""
        SELECT
            campaign.name,
            asset_group.name,
            asset_group.id,
            asset_group.status,
            asset_group.primary_status,
            asset_group.primary_status_reasons,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            metrics.all_conversions
        FROM asset_group
        WHERE segments.date DURING {date_range}
            AND campaign.advertising_channel_type = 'PERFORMANCE_MAX'
            {campaign_filter}
        ORDER BY metrics.cost_micros DESC
        LIMIT 200
    """
    
    try:
        results = _execute_raw_query(customer_id, query)
        
        if not results.get('results'):
            return "No PMax asset group data found."
        
        formatted_customer_id = format_customer_id(customer_id)
        output_lines = [f"PMax Asset Groups for Account {formatted_customer_id} | Last {days} days"]
        output_lines.append("=" * 120)
        
        for i, result in enumerate(results['results'], 1):
            campaign = result.get('campaign', {})
            ag = result.get('assetGroup', {})
            metrics = result.get('metrics', {})
            
            impressions = int(metrics.get('impressions', 0))
            clicks = int(metrics.get('clicks', 0))
            cost = int(metrics.get('costMicros', 0)) / 1_000_000
            conversions = float(metrics.get('conversions', 0))
            conv_value = float(metrics.get('conversionsValue', 0))
            
            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            cpc = (cost / clicks) if clicks > 0 else 0
            cost_per_conv = (cost / conversions) if conversions > 0 else 0
            roas = (conv_value / cost) if cost > 0 else 0
            
            status = ag.get('status', 'N/A')
            primary_status = ag.get('primaryStatus', 'N/A')
            primary_reasons = ag.get('primaryStatusReasons', [])
            
            output_lines.append(f"\n{i}. Campaign: {campaign.get('name', 'N/A')}")
            output_lines.append(f"   Asset Group: {ag.get('name', 'N/A')} (ID: {ag.get('id', 'N/A')})")
            output_lines.append(f"   Status: {status} | Primary Status: {primary_status}")
            if primary_reasons:
                output_lines.append(f"   Status Reasons: {', '.join(primary_reasons)}")
            output_lines.append(f"   Impressions: {impressions:>10,} | Clicks: {clicks:>8,} | CTR: {ctr:>6.2f}%")
            output_lines.append(f"   Cost: {cost:>12,.2f} | CPC: {cpc:>8,.2f}")
            output_lines.append(f"   Conversions: {conversions:>6.1f} | Cost/Conv: {cost_per_conv:>10,.2f} | Conv Value: {conv_value:>10,.2f} | ROAS: {roas:>6.2f}")
            output_lines.append("-" * 120)
        
        return "\n".join(output_lines)
    
    except Exception as e:
        return f"Error retrieving PMax asset groups: {str(e)}"


@mcp.tool()
async def get_pmax_asset_group_assets(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes)"),
    asset_group_id: str = Field(default="", description="Optional: specific asset group ID to inspect"),
    campaign_name_contains: str = Field(default="", description="Optional: filter by PMax campaign name")
) -> str:
    """
    List all assets (headlines, descriptions, images, videos) within PMax asset groups
    along with their performance labels.
    
    Use this to audit what creative assets are in each asset group and their quality signals.
    
    Args:
        customer_id: Google Ads customer ID
        asset_group_id: Optional specific asset group ID
        campaign_name_contains: Optional campaign name filter
    """
    filters = ["campaign.advertising_channel_type = 'PERFORMANCE_MAX'"]
    if asset_group_id:
        filters.append(f"asset_group.id = {asset_group_id}")
    if campaign_name_contains:
        filters.append(f"campaign.name LIKE '%{campaign_name_contains}%'")
    
    where_clause = " AND ".join(filters)
    
    query = f"""
        SELECT
            campaign.name,
            asset_group.name,
            asset_group.id,
            asset_group_asset.field_type,
            asset_group_asset.performance_label,
            asset_group_asset.status,
            asset.id,
            asset.name,
            asset.type,
            asset.text_asset.text,
            asset.image_asset.full_size.url,
            asset.youtube_video_asset.youtube_video_id
        FROM asset_group_asset
        WHERE {where_clause}
        ORDER BY asset_group.name, asset_group_asset.field_type
        LIMIT 500
    """
    
    try:
        results = _execute_raw_query(customer_id, query)
        
        if not results.get('results'):
            return "No PMax asset group assets found."
        
        formatted_customer_id = format_customer_id(customer_id)
        output_lines = [f"PMax Asset Group Assets for Account {formatted_customer_id}"]
        output_lines.append("=" * 120)
        
        current_ag = None
        for result in results['results']:
            campaign = result.get('campaign', {})
            ag = result.get('assetGroup', {})
            aga = result.get('assetGroupAsset', {})
            asset = result.get('asset', {})
            
            ag_name = ag.get('name', 'N/A')
            if ag_name != current_ag:
                current_ag = ag_name
                output_lines.append(f"\n--- Campaign: {campaign.get('name', 'N/A')} | Asset Group: {ag_name} (ID: {ag.get('id', 'N/A')}) ---")
            
            field_type = aga.get('fieldType', 'N/A')
            perf_label = aga.get('performanceLabel', 'UNRATED')
            status = aga.get('status', 'N/A')
            
            # Get display text based on asset type
            display_text = asset.get('textAsset', {}).get('text', '') or asset.get('name', 'N/A')
            
            yt_id = asset.get('youtubeVideoAsset', {}).get('youtubeVideoId', '')
            if yt_id:
                display_text = f"YouTube: https://youtube.com/watch?v={yt_id}"
            
            img_url = asset.get('imageAsset', {}).get('fullSize', {}).get('url', '')
            if img_url:
                display_text = f"Image: {asset.get('name', 'N/A')} ({img_url[:60]}...)"
            
            output_lines.append(f"  [{field_type}] {display_text[:80]} | Perf: {perf_label} | Status: {status}")
        
        return "\n".join(output_lines)
    
    except Exception as e:
        return f"Error retrieving PMax asset group assets: {str(e)}"


@mcp.tool()
async def get_placement_report(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes)"),
    days: int = Field(default=30, description="Number of days to look back (7, 14, 30, 90)"),
    campaign_name_contains: str = Field(default="", description="Optional: filter by campaign name"),
    min_impressions: int = Field(default=0, description="Minimum impressions to include")
) -> str:
    """
    Get placement report showing WHERE your ads appeared — websites, apps, YouTube channels.
    
    Essential for Display & PMax campaigns to identify low-quality placements to exclude.
    
    Args:
        customer_id: Google Ads customer ID
        days: Lookback period (7, 14, 30, 90)
        campaign_name_contains: Optional campaign name filter
        min_impressions: Minimum impressions threshold
    """
    date_range = _resolve_date_range(days)
    
    campaign_filter = ""
    if campaign_name_contains:
        campaign_filter = f"AND campaign.name LIKE '%{campaign_name_contains}%'"
    
    impressions_filter = ""
    if min_impressions > 0:
        impressions_filter = f"AND metrics.impressions >= {min_impressions}"
    
    query = f"""
        SELECT
            campaign.name,
            detail_placement_view.display_name,
            detail_placement_view.group_placement_target_url,
            detail_placement_view.placement_type,
            detail_placement_view.placement,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions
        FROM detail_placement_view
        WHERE segments.date DURING {date_range}
            {campaign_filter}
            {impressions_filter}
        ORDER BY metrics.impressions DESC
        LIMIT 200
    """
    
    try:
        results = _execute_raw_query(customer_id, query)
        
        if not results.get('results'):
            return "No placement data found."
        
        formatted_customer_id = format_customer_id(customer_id)
        output_lines = [f"Placement Report for Account {formatted_customer_id} | Last {days} days"]
        output_lines.append("=" * 130)
        
        for i, result in enumerate(results['results'], 1):
            campaign = result.get('campaign', {})
            dpv = result.get('detailPlacementView', {})
            metrics = result.get('metrics', {})
            
            impressions = int(metrics.get('impressions', 0))
            clicks = int(metrics.get('clicks', 0))
            cost = int(metrics.get('costMicros', 0)) / 1_000_000
            conversions = float(metrics.get('conversions', 0))
            
            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            cpc = (cost / clicks) if clicks > 0 else 0
            
            display_name = dpv.get('displayName', 'N/A')
            target_url = dpv.get('groupPlacementTargetUrl', 'N/A')
            placement_type = dpv.get('placementType', 'N/A')
            
            output_lines.append(f"\n{i}. {display_name}")
            output_lines.append(f"   URL: {target_url}")
            output_lines.append(f"   Type: {placement_type} | Campaign: {campaign.get('name', 'N/A')}")
            output_lines.append(f"   Impressions: {impressions:>10,} | Clicks: {clicks:>6,} | CTR: {ctr:>6.2f}%")
            output_lines.append(f"   Cost: {cost:>10,.2f} | CPC: {cpc:>8,.2f} | Conversions: {conversions:>6.1f}")
        
        output_lines.append(f"\n{'=' * 130}")
        output_lines.append(f"Total placements: {len(results['results'])}")
        
        return "\n".join(output_lines)
    
    except Exception as e:
        return f"Error retrieving placement report: {str(e)}"


@mcp.tool()
async def get_search_terms(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes)"),
    days: int = Field(default=30, description="Number of days to look back (7, 14, 30, 90)"),
    campaign_name_contains: str = Field(default="", description="Optional: filter by campaign name"),
    min_impressions: int = Field(default=10, description="Minimum impressions to include"),
    sort_by: str = Field(default="impressions", description="Sort by: 'impressions', 'clicks', 'conversions', 'cost'")
) -> str:
    """
    Get search term report showing actual user queries that triggered your ads.
    
    Use this to find new keyword opportunities and negative keyword candidates.
    Includes a summary section flagging potential negatives (high cost, zero conversions).
    
    Args:
        customer_id: Google Ads customer ID
        days: Lookback period
        campaign_name_contains: Optional campaign name filter
        min_impressions: Minimum impressions threshold
        sort_by: Sort metric
    """
    date_range = _resolve_date_range(days)
    
    campaign_filter = ""
    if campaign_name_contains:
        campaign_filter = f"AND campaign.name LIKE '%{campaign_name_contains}%'"
    
    sort_field_map = {
        'impressions': 'metrics.impressions',
        'clicks': 'metrics.clicks',
        'conversions': 'metrics.conversions',
        'cost': 'metrics.cost_micros'
    }
    sort_field = sort_field_map.get(sort_by, 'metrics.impressions')
    
    query = f"""
        SELECT
            campaign.name,
            ad_group.name,
            search_term_view.search_term,
            search_term_view.status,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value
        FROM search_term_view
        WHERE segments.date DURING {date_range}
            AND metrics.impressions >= {min_impressions}
            {campaign_filter}
        ORDER BY {sort_field} DESC
        LIMIT 300
    """
    
    try:
        results = _execute_raw_query(customer_id, query)
        
        if not results.get('results'):
            return "No search term data found."
        
        formatted_customer_id = format_customer_id(customer_id)
        output_lines = [f"Search Terms Report for Account {formatted_customer_id} | Last {days} days"]
        output_lines.append("=" * 130)
        
        negative_candidates = []
        
        for i, result in enumerate(results['results'], 1):
            campaign = result.get('campaign', {})
            ad_group = result.get('adGroup', {})
            stv = result.get('searchTermView', {})
            metrics = result.get('metrics', {})
            
            search_term = stv.get('searchTerm', 'N/A')
            status = stv.get('status', 'N/A')
            impressions = int(metrics.get('impressions', 0))
            clicks = int(metrics.get('clicks', 0))
            cost = int(metrics.get('costMicros', 0)) / 1_000_000
            conversions = float(metrics.get('conversions', 0))
            conv_value = float(metrics.get('conversionsValue', 0))
            
            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            cpc = (cost / clicks) if clicks > 0 else 0
            
            output_lines.append(f"\n{i}. \"{search_term}\"")
            output_lines.append(f"   Campaign: {campaign.get('name', 'N/A')} | Ad Group: {ad_group.get('name', 'N/A')}")
            output_lines.append(f"   Status: {status}")
            output_lines.append(f"   Impressions: {impressions:>8,} | Clicks: {clicks:>6,} | CTR: {ctr:>6.2f}%")
            output_lines.append(f"   Cost: {cost:>10,.2f} | CPC: {cpc:>8,.2f} | Conversions: {conversions:>5.1f} | Conv Value: {conv_value:>10,.2f}")
            
            # Flag potential negative keywords: cost > threshold, 0 conversions
            if cost > 0 and conversions == 0 and clicks >= 3:
                negative_candidates.append({
                    'term': search_term,
                    'cost': cost,
                    'clicks': clicks,
                    'campaign': campaign.get('name', 'N/A')
                })
        
        # Negative keyword suggestions
        if negative_candidates:
            output_lines.append(f"\n{'=' * 130}")
            output_lines.append(f"⚠️  NEGATIVE KEYWORD CANDIDATES ({len(negative_candidates)} terms with cost but 0 conversions):")
            output_lines.append("-" * 80)
            
            neg_sorted = sorted(negative_candidates, key=lambda x: x['cost'], reverse=True)
            for nc in neg_sorted[:20]:
                output_lines.append(f"  \"{nc['term']}\" — Cost: {nc['cost']:,.2f} | Clicks: {nc['clicks']} | Campaign: {nc['campaign']}")
        
        return "\n".join(output_lines)
    
    except Exception as e:
        return f"Error retrieving search terms: {str(e)}"


@mcp.tool()
async def get_schedule_performance(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes)"),
    days: int = Field(default=30, description="Number of days to look back (7, 14, 30, 90)"),
    breakdown: str = Field(default="day_of_week", description="Breakdown: 'day_of_week', 'hour', 'device'"),
    campaign_name_contains: str = Field(default="", description="Optional: filter by campaign name")
) -> str:
    """
    Get performance broken down by WHEN or WHERE ads show — day of week, hour of day, or device.
    
    Use this to optimize ad scheduling and device bid adjustments.
    
    Args:
        customer_id: Google Ads customer ID
        days: Lookback period
        breakdown: 'day_of_week', 'hour', or 'device'
        campaign_name_contains: Optional campaign name filter
    """
    date_range = _resolve_date_range(days)
    
    segment_map = {
        'day_of_week': 'segments.day_of_week',
        'hour': 'segments.hour',
        'device': 'segments.device'
    }
    segment = segment_map.get(breakdown, 'segments.day_of_week')
    
    campaign_filter = ""
    if campaign_name_contains:
        campaign_filter = f"AND campaign.name LIKE '%{campaign_name_contains}%'"
    
    query = f"""
        SELECT
            campaign.name,
            {segment},
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value
        FROM campaign
        WHERE segments.date DURING {date_range}
            AND campaign.status = 'ENABLED'
            {campaign_filter}
        ORDER BY {segment}
    """
    
    try:
        results = _execute_raw_query(customer_id, query)
        
        if not results.get('results'):
            return "No schedule performance data found."
        
        formatted_customer_id = format_customer_id(customer_id)
        output_lines = [f"Schedule Performance for Account {formatted_customer_id} | Last {days} days | By: {breakdown}"]
        output_lines.append("=" * 120)
        
        # Aggregate by segment value across campaigns
        agg = {}
        for result in results['results']:
            segments = result.get('segments', {})
            metrics = result.get('metrics', {})
            
            segment_value = segments.get(breakdown.replace('_', ''), '') or segments.get('dayOfWeek', '') or segments.get('hour', '') or segments.get('device', '') or 'N/A'
            # Handle camelCase variations
            for key in segments:
                segment_value = str(segments[key])
                break
            
            if segment_value not in agg:
                agg[segment_value] = {'impressions': 0, 'clicks': 0, 'cost_micros': 0, 'conversions': 0, 'conv_value': 0}
            
            agg[segment_value]['impressions'] += int(metrics.get('impressions', 0))
            agg[segment_value]['clicks'] += int(metrics.get('clicks', 0))
            agg[segment_value]['cost_micros'] += int(metrics.get('costMicros', 0))
            agg[segment_value]['conversions'] += float(metrics.get('conversions', 0))
            agg[segment_value]['conv_value'] += float(metrics.get('conversionsValue', 0))
        
        # Format output
        output_lines.append(f"\n{'Segment':<15} | {'Impressions':>12} | {'Clicks':>8} | {'CTR':>7} | {'Cost':>12} | {'CPC':>8} | {'Conv':>6} | {'Cost/Conv':>10} | {'ROAS':>6}")
        output_lines.append("-" * 120)
        
        for seg_val, data in sorted(agg.items()):
            impressions = data['impressions']
            clicks = data['clicks']
            cost = data['cost_micros'] / 1_000_000
            conversions = data['conversions']
            conv_value = data['conv_value']
            
            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            cpc = (cost / clicks) if clicks > 0 else 0
            cost_per_conv = (cost / conversions) if conversions > 0 else 0
            roas = (conv_value / cost) if cost > 0 else 0
            
            output_lines.append(f"{str(seg_val):<15} | {impressions:>12,} | {clicks:>8,} | {ctr:>6.2f}% | {cost:>12,.2f} | {cpc:>8,.2f} | {conversions:>6.1f} | {cost_per_conv:>10,.2f} | {roas:>6.2f}")
        
        return "\n".join(output_lines)
    
    except Exception as e:
        return f"Error retrieving schedule performance: {str(e)}"


@mcp.tool()
async def get_keyword_ideas(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes)"),
    keywords: str = Field(description="Seed keywords (use | as separator for multiple). Example: 'đại học quốc tế|du học đức|học bổng đại học'"),
    language_id: str = Field(default="1040", description="Language criterion ID. 1000=English, 1040=Vietnamese"),
    location_ids: str = Field(default="2704", description="Geo target criterion IDs (use | as separator). 2704=Vietnam, 2840=US"),
    page_size: int = Field(default=50, description="Number of keyword ideas to return (max 100)"),
    start_year: int = Field(default=0, description="Custom date range start year (e.g. 2024). Leave 0 for default rolling 12 months."),
    start_month: int = Field(default=0, description="Custom date range start month (1-12). Leave 0 for default."),
    end_year: int = Field(default=0, description="Custom date range end year (e.g. 2025). Leave 0 for default."),
    end_month: int = Field(default=0, description="Custom date range end month (1-12). Leave 0 for default.")
) -> str:
    """
    Get keyword ideas with search volume data — replacement for Google Keyword Planner UI.
    
    Returns: keyword text, monthly search volumes, competition level, bid estimates.
    
    IMPORTANT: Use | (pipe) to separate multiple keywords, NOT comma.
    
    DATE RANGE:
    - Default (no start/end): Rolling 12 months (same as Google Keyword Planner default)
    - Custom: Set start_year/start_month and end_year/end_month to get specific period
      Example: start_year=2024, start_month=5, end_year=2024, end_month=8 → May-Aug 2024
    - Supports historical data (older than 12 months)
    - Useful for: seasonality analysis, YoY comparison, custom FY periods
    
    Common language IDs: 1000=English, 1040=Vietnamese, 1015=Japanese
    Common location IDs: 2704=Vietnam, 2840=US, 2826=UK, 2392=Japan
    """
    MONTH_NAMES = {
        1: "JANUARY", 2: "FEBRUARY", 3: "MARCH", 4: "APRIL",
        5: "MAY", 6: "JUNE", 7: "JULY", 8: "AUGUST",
        9: "SEPTEMBER", 10: "OCTOBER", 11: "NOVEMBER", 12: "DECEMBER"
    }
    
    try:
        creds = get_credentials()
        headers = get_headers(creds)
        
        formatted_customer_id = format_customer_id(customer_id)
        
        # Build keyword seed — use | as separator to avoid conflict with API
        keyword_list = [k.strip() for k in keywords.split('|') if k.strip()]
        
        # Build geo targets
        geo_targets = []
        for loc_id in location_ids.split('|'):
            loc_id = loc_id.strip()
            if loc_id:
                geo_targets.append(f"geoTargetConstants/{loc_id}")
        
        # KeywordPlanIdeaService endpoint
        url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{formatted_customer_id}:generateKeywordIdeas"
        
        payload = {
            "keywordSeed": {
                "keywords": keyword_list
            },
            "language": f"languageConstants/{language_id}",
            "geoTargetConstants": geo_targets,
            "keywordPlanNetwork": "GOOGLE_SEARCH",
            "pageSize": min(page_size, 100)
        }
        
        # Add custom date range if specified
        has_custom_range = all([start_year, start_month, end_year, end_month])
        if has_custom_range:
            if start_month < 1 or start_month > 12 or end_month < 1 or end_month > 12:
                return "Error: start_month and end_month must be between 1 and 12."
            
            payload["historicalMetricsOptions"] = {
                "yearMonthRange": {
                    "start": {"year": start_year, "month": MONTH_NAMES[start_month]},
                    "end": {"year": end_year, "month": MONTH_NAMES[end_month]}
                }
            }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            return f"Error getting keyword ideas: {response.text}"
        
        results = response.json()
        keyword_ideas = results.get('results', [])
        
        if not keyword_ideas:
            return "No keyword ideas found for the given seeds."
        
        # Build header
        date_range_str = "Rolling 12 months"
        if has_custom_range:
            date_range_str = f"{MONTH_NAMES[start_month][:3]} {start_year} → {MONTH_NAMES[end_month][:3]} {end_year}"
        
        output_lines = [f"Keyword Ideas for Account {formatted_customer_id}"]
        output_lines.append(f"Seeds: {', '.join(keyword_list)} | Language: {language_id} | Locations: {location_ids} | Period: {date_range_str}")
        output_lines.append("=" * 140)
        
        # Build column headers — show monthly breakdown if custom range, otherwise avg
        first_km = keyword_ideas[0].get('keywordIdeaMetrics', {})
        first_months = first_km.get('monthlySearchVolumes', [])
        
        show_monthly = has_custom_range and len(first_months) <= 12
        
        if show_monthly and first_months:
            # Monthly breakdown header
            month_headers = [f"{m['month'][:3]} {str(m['year'])[2:]}" for m in first_months]
            header = f"{'#':<4} {'Keyword':<40} | " + " | ".join(f"{mh:>8}" for mh in month_headers) + f" | {'Avg':>8} | {'Comp':>10}"
            output_lines.append(f"\n{header}")
            output_lines.append("-" * len(header))
            
            for i, idea in enumerate(keyword_ideas, 1):
                text = idea.get('text', 'N/A')
                km = idea.get('keywordIdeaMetrics', {})
                monthly_volumes = km.get('monthlySearchVolumes', [])
                competition = km.get('competition', 'UNSPECIFIED')
                comp_index = km.get('competitionIndex', '')
                comp_display = f"{competition}({comp_index})" if comp_index else competition
                
                volumes = [int(m.get('monthlySearches', 0)) for m in monthly_volumes]
                avg = sum(volumes) // len(volumes) if volumes else 0
                
                vol_str = " | ".join(f"{v:>8,}" for v in volumes)
                output_lines.append(f"{i:<4} {text:<40} | {vol_str} | {avg:>8,} | {comp_display:>10}")
        else:
            # Summary view (default rolling 12 months)
            output_lines.append(f"\n{'#':<4} {'Keyword':<45} | {'Avg Monthly':>12} | {'Competition':>12} | {'Low Bid':>12} | {'High Bid':>12}")
            output_lines.append("-" * 130)
            
            for i, idea in enumerate(keyword_ideas, 1):
                text = idea.get('text', 'N/A')
                km = idea.get('keywordIdeaMetrics', {})
                competition = km.get('competition', 'UNSPECIFIED')
                
                monthly_volumes = km.get('monthlySearchVolumes', [])
                if monthly_volumes:
                    total_searches = sum(int(m.get('monthlySearches', 0)) for m in monthly_volumes)
                    avg_monthly = total_searches // len(monthly_volumes)
                else:
                    avg_monthly = int(km.get('avgMonthlySearches', 0))
                
                low_bid_micros = km.get('lowTopOfPageBidMicros', 0)
                high_bid_micros = km.get('highTopOfPageBidMicros', 0)
                low_bid = int(low_bid_micros) / 1_000_000 if low_bid_micros else 0
                high_bid = int(high_bid_micros) / 1_000_000 if high_bid_micros else 0
                
                comp_index = km.get('competitionIndex', '')
                comp_display = f"{competition}({comp_index})" if comp_index else competition
                
                output_lines.append(f"{i:<4} {text:<45} | {avg_monthly:>12,} | {comp_display:>12} | {low_bid:>12,.0f} | {high_bid:>12,.0f}")
        
        output_lines.append(f"\n{'=' * 140}")
        output_lines.append(f"Total ideas: {len(keyword_ideas)} | Period: {date_range_str}")
        if not has_custom_range:
            output_lines.append("Note: Bid estimates are in account currency (micros/1M). Competition: LOW/MEDIUM/HIGH.")
        output_lines.append("Tip: Add start_year/start_month/end_year/end_month for custom date range & monthly breakdown.")
        
        return "\n".join(output_lines)
    
    except Exception as e:
        return f"Error getting keyword ideas: {str(e)}"


@mcp.tool()
async def get_video_performance(
    customer_id: str = Field(description="Google Ads customer ID (10 digits, no dashes)"),
    days: int = Field(default=30, description="Number of days to look back (7, 14, 30, 90)"),
    campaign_name_contains: str = Field(default="", description="Optional: filter by campaign name")
) -> str:
    """
    Get video ad performance metrics — views, view rate, watch time, conversions.
    
    Essential for YouTube/Video campaigns and PMax with video assets.
    
    Args:
        customer_id: Google Ads customer ID
        days: Lookback period
        campaign_name_contains: Optional campaign name filter
    """
    date_range = _resolve_date_range(days)
    
    campaign_filter = ""
    if campaign_name_contains:
        campaign_filter = f"AND campaign.name LIKE '%{campaign_name_contains}%'"
    
    query = f"""
        SELECT
            campaign.name,
            ad_group.name,
            video.id,
            video.title,
            video.duration_millis,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.video_views,
            metrics.video_view_rate,
            metrics.video_quartile_p25_rate,
            metrics.video_quartile_p50_rate,
            metrics.video_quartile_p75_rate,
            metrics.video_quartile_p100_rate
        FROM video
        WHERE segments.date DURING {date_range}
            {campaign_filter}
        ORDER BY metrics.impressions DESC
        LIMIT 100
    """
    
    try:
        results = _execute_raw_query(customer_id, query)
        
        if not results.get('results'):
            return "No video performance data found."
        
        formatted_customer_id = format_customer_id(customer_id)
        output_lines = [f"Video Performance for Account {formatted_customer_id} | Last {days} days"]
        output_lines.append("=" * 120)
        
        for i, result in enumerate(results['results'], 1):
            campaign = result.get('campaign', {})
            ad_group = result.get('adGroup', {})
            video = result.get('video', {})
            metrics = result.get('metrics', {})
            
            impressions = int(metrics.get('impressions', 0))
            clicks = int(metrics.get('clicks', 0))
            cost = int(metrics.get('costMicros', 0)) / 1_000_000
            conversions = float(metrics.get('conversions', 0))
            video_views = int(metrics.get('videoViews', 0))
            view_rate = float(metrics.get('videoViewRate', 0)) * 100
            
            q25 = float(metrics.get('videoQuartileP25Rate', 0)) * 100
            q50 = float(metrics.get('videoQuartileP50Rate', 0)) * 100
            q75 = float(metrics.get('videoQuartileP75Rate', 0)) * 100
            q100 = float(metrics.get('videoQuartileP100Rate', 0)) * 100
            
            duration_ms = int(video.get('durationMillis', 0))
            duration_sec = duration_ms / 1000 if duration_ms else 0
            
            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            cpv = (cost / video_views) if video_views > 0 else 0
            
            output_lines.append(f"\n{i}. {video.get('title', 'N/A')} ({duration_sec:.0f}s)")
            output_lines.append(f"   Video ID: {video.get('id', 'N/A')}")
            output_lines.append(f"   Campaign: {campaign.get('name', 'N/A')} | Ad Group: {ad_group.get('name', 'N/A')}")
            output_lines.append(f"   Impressions: {impressions:>10,} | Views: {video_views:>8,} | View Rate: {view_rate:>6.2f}%")
            output_lines.append(f"   Clicks: {clicks:>8,} | CTR: {ctr:>6.2f}% | Cost: {cost:>10,.2f} | CPV: {cpv:>8,.4f}")
            output_lines.append(f"   Conversions: {conversions:>6.1f}")
            output_lines.append(f"   Watch Progress: 25%={q25:.1f}% | 50%={q50:.1f}% | 75%={q75:.1f}% | 100%={q100:.1f}%")
            output_lines.append("-" * 120)
        
        return "\n".join(output_lines)
    
    except Exception as e:
        return f"Error retrieving video performance: {str(e)}"


@mcp.tool()
async def get_cross_account_report(
    customer_ids: str = Field(description="Comma-separated list of Google Ads customer IDs. Example: 'ID1,ID2'"),
    report_type: str = Field(default="campaign", description="Report type: 'campaign', 'ad_group', 'keyword', 'asset'"),
    days: int = Field(default=30, description="Number of days to look back (7, 14, 30, 90)"),
    top_n: int = Field(default=10, description="Top N items per account to include")
) -> str:
    """
    Pull the same report across multiple accounts in one command.
    
    Perfect for agency workflows: compare VGU vs FEC vs AGS performance in one view.
    
    Args:
        customer_ids: Comma-separated customer IDs
        report_type: What to report on — campaign, ad_group, keyword, or asset
        days: Lookback period
        top_n: Top N results per account
    """
    date_range = _resolve_date_range(days)
    
    # Build query based on report type
    query_map = {
        'campaign': f"""
            SELECT campaign.name, campaign.status, metrics.impressions, metrics.clicks,
                   metrics.cost_micros, metrics.conversions, metrics.conversions_value
            FROM campaign
            WHERE segments.date DURING {date_range} AND campaign.status = 'ENABLED'
            ORDER BY metrics.cost_micros DESC
            LIMIT {top_n}
        """,
        'ad_group': f"""
            SELECT campaign.name, ad_group.name, ad_group.status, metrics.impressions,
                   metrics.clicks, metrics.cost_micros, metrics.conversions
            FROM ad_group
            WHERE segments.date DURING {date_range} AND ad_group.status = 'ENABLED'
            ORDER BY metrics.cost_micros DESC
            LIMIT {top_n}
        """,
        'keyword': f"""
            SELECT campaign.name, ad_group.name, ad_group_criterion.keyword.text,
                   ad_group_criterion.keyword.match_type, metrics.impressions,
                   metrics.clicks, metrics.cost_micros, metrics.conversions
            FROM keyword_view
            WHERE segments.date DURING {date_range}
            ORDER BY metrics.cost_micros DESC
            LIMIT {top_n}
        """,
        'asset': f"""
            SELECT campaign.name, ad_group_ad_asset_view.field_type, asset.text_asset.text,
                   asset.name, ad_group_ad_asset_view.performance_label,
                   metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions
            FROM ad_group_ad_asset_view
            WHERE segments.date DURING {date_range}
            ORDER BY metrics.impressions DESC
            LIMIT {top_n}
        """
    }
    
    query = query_map.get(report_type, query_map['campaign'])
    
    ids = [cid.strip() for cid in customer_ids.split(',') if cid.strip()]
    
    output_lines = [f"Cross-Account {report_type.title()} Report | Last {days} days"]
    output_lines.append(f"Accounts: {', '.join(ids)}")
    output_lines.append("=" * 130)
    
    for cid in ids:
        formatted_cid = format_customer_id(cid)
        output_lines.append(f"\n{'#' * 60}")
        output_lines.append(f"ACCOUNT: {formatted_cid}")
        output_lines.append(f"{'#' * 60}")
        
        try:
            results = _execute_raw_query(cid, query)
            
            if not results.get('results'):
                output_lines.append("  No data found for this account.")
                continue
            
            for i, result in enumerate(results['results'], 1):
                metrics = result.get('metrics', {})
                impressions = int(metrics.get('impressions', 0))
                clicks = int(metrics.get('clicks', 0))
                cost = int(metrics.get('costMicros', 0)) / 1_000_000
                conversions = float(metrics.get('conversions', 0))
                
                ctr = (clicks / impressions * 100) if impressions > 0 else 0
                cost_per_conv = (cost / conversions) if conversions > 0 else 0
                
                # Build display name based on report type
                if report_type == 'campaign':
                    name = result.get('campaign', {}).get('name', 'N/A')
                elif report_type == 'ad_group':
                    name = f"{result.get('campaign', {}).get('name', 'N/A')} > {result.get('adGroup', {}).get('name', 'N/A')}"
                elif report_type == 'keyword':
                    kw = result.get('adGroupCriterion', {}).get('keyword', {})
                    name = f"{kw.get('text', 'N/A')} [{kw.get('matchType', 'N/A')}]"
                elif report_type == 'asset':
                    asset = result.get('asset', {})
                    asset_view = result.get('adGroupAdAssetView', {})
                    name = f"[{asset_view.get('fieldType', '?')}] {asset.get('textAsset', {}).get('text', '') or asset.get('name', 'N/A')}"
                else:
                    name = 'N/A'
                
                output_lines.append(f"  {i}. {name[:70]}")
                output_lines.append(f"     Imp: {impressions:>10,} | Clicks: {clicks:>8,} | CTR: {ctr:>6.2f}% | Cost: {cost:>10,.2f} | Conv: {conversions:>5.1f} | CPA: {cost_per_conv:>10,.2f}")
        
        except Exception as e:
            output_lines.append(f"  Error: {str(e)}")
    
    return "\n".join(output_lines)


@mcp.tool()
async def search_geo_targets(
    location_names: str = Field(description="Location names to search (use | as separator). Example: 'Da Nang|Hue|Ho Chi Minh City' or 'Vietnam|Thailand|Germany'"),
    country_code: str = Field(default="", description="Optional 2-letter country code to narrow results. Example: 'VN', 'TH', 'DE'. Leave empty for worldwide search."),
    locale: str = Field(default="en", description="Display locale: 'en' for English names, 'vi' for Vietnamese names, etc."),
    target_types: str = Field(default="", description="Filter by target type (use | separator). Example: 'Country|Province|City'. Leave empty for all types. Options: Country, State, Province, City, District, Municipality, Neighborhood.")
) -> str:
    """
    Search Google Ads geo target locations by name — returns criterion IDs for use in get_keyword_ideas.
    
    Use this to resolve location names (e.g. 'Đà Nẵng', 'Bavaria', 'Lagos') into criterion IDs
    that get_keyword_ideas needs for its location_ids parameter.
    
    Works for ANY location worldwide: countries, states, provinces, cities, districts.
    
    IMPORTANT: Use | (pipe) to separate multiple location names, NOT comma.
    
    Example workflow:
    1. search_geo_targets('Da Nang|Hue|Quang Nam', country_code='VN')
       → Da Nang=9047170, Hue=9040349, Quang Nam=9040351
    2. get_keyword_ideas(keywords='...', location_ids='9047170|9040349|9040351')
    
    Args:
        location_names: Pipe-separated location names to search
        country_code: Optional country code to filter results (e.g. 'VN', 'DE')
        locale: Display language for location names ('en', 'vi', etc.)
        target_types: Optional filter by location type ('Country|Province|City')
    """
    try:
        creds = get_credentials()
        headers = get_headers(creds)
        
        # Parse location names
        names = [n.strip() for n in location_names.split('|') if n.strip()]
        
        if not names:
            return "Error: No location names provided."
        
        # Parse target type filter
        type_filter = set()
        if target_types:
            type_filter = {t.strip().upper() for t in target_types.split('|') if t.strip()}
        
        # GeoTargetConstantService endpoint
        url = f"https://googleads.googleapis.com/{API_VERSION}/geoTargetConstants:suggest"
        
        payload = {
            "locale": locale,
            "locationNames": {
                "names": names
            }
        }
        
        if country_code:
            payload["countryCode"] = country_code.upper()
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            return f"Error searching geo targets: {response.text}"
        
        results = response.json()
        suggestions = results.get('geoTargetConstantSuggestions', [])
        
        if not suggestions:
            return f"No geo targets found for: {', '.join(names)}"
        
        # Group results by search term for cleaner output
        # Prioritize: Country > State > Province > City > District > others
        TYPE_PRIORITY = {
            'COUNTRY': 1, 'STATE': 2, 'PROVINCE': 3, 'CITY': 4,
            'MUNICIPALITY': 5, 'DISTRICT': 6, 'NEIGHBORHOOD': 7
        }
        
        output_lines = [f"Geo Target Search Results"]
        output_lines.append(f"Query: {', '.join(names)} | Country: {country_code or 'All'} | Locale: {locale}")
        if type_filter:
            output_lines.append(f"Filter: {', '.join(type_filter)}")
        output_lines.append("=" * 110)
        
        # Quick reference section — top match per search term
        output_lines.append(f"\n📋 QUICK REFERENCE (top match per search term — copy IDs for get_keyword_ideas):")
        output_lines.append("-" * 80)
        
        quick_ids = []
        seen_names = set()
        
        # Sort by type priority so top matches are most useful
        sorted_suggestions = sorted(
            suggestions,
            key=lambda x: TYPE_PRIORITY.get(x.get('geoTargetConstant', {}).get('targetType', ''), 99)
        )
        
        for suggestion in sorted_suggestions:
            gtc = suggestion.get('geoTargetConstant', {})
            search_term = suggestion.get('searchTerm', '')
            target_type = gtc.get('targetType', '')
            
            # Apply type filter
            if type_filter and target_type.upper() not in type_filter:
                continue
            
            # Only show first match per search term for quick reference
            if search_term.lower() not in seen_names:
                seen_names.add(search_term.lower())
                geo_id = gtc.get('id', '')
                name = gtc.get('name', '')
                canonical = gtc.get('canonicalName', '')
                quick_ids.append(str(geo_id))
                output_lines.append(f"  {name:<30} | ID: {geo_id:<12} | {target_type:<10} | {canonical}")
        
        output_lines.append(f"\n  → location_ids for get_keyword_ideas: {' | '.join(quick_ids)}")
        output_lines.append(f"    (copy-paste ready: {'|'.join(quick_ids)})")
        
        # Full results section
        output_lines.append(f"\n{'=' * 110}")
        output_lines.append(f"📊 ALL RESULTS ({len(suggestions)} matches):")
        output_lines.append(f"{'#':<4} {'Name':<30} | {'ID':<12} | {'Type':<14} | {'Country':<8} | {'Path'}")
        output_lines.append("-" * 110)
        
        count = 0
        for suggestion in sorted_suggestions:
            gtc = suggestion.get('geoTargetConstant', {})
            target_type = gtc.get('targetType', '')
            
            # Apply type filter
            if type_filter and target_type.upper() not in type_filter:
                continue
            
            count += 1
            name = gtc.get('name', 'N/A')
            geo_id = gtc.get('id', 'N/A')
            country = gtc.get('countryCode', 'N/A')
            canonical = gtc.get('canonicalName', '')
            
            output_lines.append(f"{count:<4} {name:<30} | {geo_id:<12} | {target_type:<14} | {country:<8} | {canonical}")
        
        output_lines.append(f"\n{'=' * 110}")
        output_lines.append(f"Total: {count} results")
        
        return "\n".join(output_lines)
    
    except Exception as e:
        return f"Error searching geo targets: {str(e)}"


# ============================================================================
# RESOURCES & PROMPTS
# ============================================================================

@mcp.resource("gaql://reference")
def gaql_reference() -> str:
    """Google Ads Query Language (GAQL) reference documentation."""
    return """
    # Google Ads Query Language (GAQL) Reference
    
    ## Basic Query Structure
    SELECT field1, field2, ... 
    FROM resource_type
    WHERE condition
    ORDER BY field [ASC|DESC]
    LIMIT n
    
    ## Common Resources
    - campaign, ad_group, ad_group_ad, keyword_view
    - search_term_view, ad_group_ad_asset_view
    - asset_group, asset_group_asset (PMax)
    - detail_placement_view, video
    - campaign_asset, ad_group_asset
    
    ## Common Metrics
    - metrics.impressions, metrics.clicks, metrics.ctr
    - metrics.cost_micros, metrics.average_cpc
    - metrics.conversions, metrics.conversions_value
    - metrics.video_views, metrics.video_view_rate
    
    ## Date Ranges
    - LAST_7_DAYS, LAST_14_DAYS, LAST_30_DAYS, LAST_90_DAYS
    - BETWEEN '2023-01-01' AND '2023-01-31'
    
    ## Tips
    - Cost values are in micros (1,000,000 = 1 unit of currency)
    - Protobuf omits zero-value fields — always use .get(field, 0)
    """

@mcp.prompt("google_ads_workflow")
def google_ads_workflow() -> str:
    """Provides guidance on the recommended workflow for using Google Ads tools."""
    return """
    Recommended workflow:
    
    1. list_accounts() — find your account IDs
    2. get_account_currency(customer_id) — check currency
    3. Choose your analysis:
       - get_campaign_performance() — campaign overview
       - get_asset_performance() — headline/description/image metrics ⭐ NEW
       - get_pmax_asset_groups() — PMax asset group breakdown ⭐ NEW
       - get_pmax_asset_group_assets() — inspect PMax assets ⭐ NEW
       - get_placement_report() — where ads appeared ⭐ NEW
       - get_search_terms() — search queries + negative suggestions ⭐ NEW
       - get_schedule_performance() — day/hour/device breakdown ⭐ NEW
       - get_keyword_ideas() — keyword planner replacement (supports custom date range) ⭐ NEW
       - search_geo_targets() — resolve location names to criterion IDs ⭐ NEW
       - get_video_performance() — YouTube/video metrics ⭐ NEW
       - get_cross_account_report() — multi-account comparison ⭐ NEW
    4. run_gaql() — custom queries for anything else
    
    Keyword research workflow:
    a. search_geo_targets('Da Nang|Hue') → get criterion IDs
    b. get_keyword_ideas(keywords='...', location_ids='ID1|ID2') → search volume + ideas
    c. Add start_year/start_month/end_year/end_month for custom date range
    """

@mcp.prompt("gaql_help")
def gaql_help() -> str:
    """Provides assistance for writing GAQL queries."""
    return """
    Common GAQL queries:
    
    ## Campaign performance
    SELECT campaign.name, metrics.clicks, metrics.impressions, metrics.cost_micros
    FROM campaign WHERE segments.date DURING LAST_30_DAYS
    
    ## Keyword performance
    SELECT keyword.text, keyword.match_type, metrics.clicks, metrics.conversions
    FROM keyword_view WHERE segments.date DURING LAST_30_DAYS
    
    ## Asset performance (use get_asset_performance tool instead for better output)
    SELECT asset.text_asset.text, ad_group_ad_asset_view.performance_label, metrics.impressions
    FROM ad_group_ad_asset_view WHERE segments.date DURING LAST_30_DAYS
    """


if __name__ == "__main__":
    mcp.run(transport="stdio")
