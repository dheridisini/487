import httpx
from datetime import datetime, timedelta
from config import ADSTERRA_API_KEY

async def get_stats(start_date, end_date, domain=None, placement=None, group_by="date"):
    base_url = "https://api3.adsterratools.com/publisher/stats.json"
    params = {
        "start_date": start_date,
        "finish_date": end_date,
        "group_by": group_by
    }

    if domain:
        params["domain"] = domain
    if placement:
        params["placement"] = placement

    headers = {
        "Accept": "application/json",
        "X-API-Key": ADSTERRA_API_KEY
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(base_url, headers=headers, params=params)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"API Error: {e}")
            return None

async def get_placements(domain_id):
    url = f"https://api3.adsterratools.com/publisher/domain/{domain_id}/placements.json"
    headers = {
        "X-API-Key": ADSTERRA_API_KEY,
        "Accept": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("items", [])
    except Exception as e:
        print(f"Placements API Error: {e}")
    
    return []

def calculate_summary(stats):
    summary = {
        "revenue": 0,
        "impression": 0,
        "clicks": 0,
        "ctr": 0,
        "cpm": 0,
    }

    if not stats or 'items' not in stats:
        return summary

    items = stats['items']
    if not items:
        return {
            "revenue": stats.get("revenue", 0),
            "impression": stats.get("impression", 0),
            "clicks": stats.get("clicks", 0),
            "ctr": stats.get("ctr", 0),
            "cpm": stats.get("cpm", 0),
        }

    total_revenue = sum(float(item.get("revenue", 0) or 0) for item in items)
    total_impression = sum(int(item.get("impression", 0) or 0) for item in items)
    total_clicks = sum(int(item.get("clicks", 0) or 0) for item in items)
    
    summary['revenue'] = total_revenue
    summary['impression'] = total_impression
    summary['clicks'] = total_clicks
    
    if total_impression > 0:
        summary['ctr'] = (total_clicks / total_impression) * 100
        summary['cpm'] = (total_revenue / total_impression) * 1000
    
    return summary

def format_summary(summary, start_date=None, end_date=None):
    text = (
        f"💵 Earnings: ${summary['revenue']:.3f}\n"
        f"👀 Impressions: {summary['impression']:,}\n"
        f"🖱 Clicks: {summary['clicks']:,}\n"
        f"🎯 CTR: {summary['ctr']:.2f}%\n"
        f"📊 CPM: ${summary['cpm']:.3f}"
    )
    
    if start_date and end_date:
        text += f"\n\n📆 {start_date} s/d {end_date}"

    return text


def format_stats(stats, group_by):
    if not stats or 'items' not in stats or not stats['items']:
        return "No data available for the selected filters."
    
    items = stats['items']
    message = ""
    
    if group_by == 'date':
        for item in items:
            date = item.get('date', 'N/A')
            message += (
                f"\n📅 {date}\n"
                f"Impressions: {item.get('impression', 0):,}\n"
                f"Clicks: {item.get('clicks', 0):,}\n"
                f"CTR: {item.get('ctr', 0):.2f}%\n"
                f"Earnings: ${float(item.get('revenue', 0)):.3f}\n"
                f"CPM: ${float(item.get('cpm', 0)):.3f}\n"
            )
    else:  # country
        for item in items:
            country = item.get('country', 'N/A')
            message += (
                f"\n🌍 {country}\n"
                f"Impressions: {item.get('impression', 0):,}\n"
                f"Clicks: {item.get('clicks', 0):,}\n"
                f"CTR: {item.get('ctr', 0):.2f}%\n"
                f"Earnings: ${float(item.get('revenue', 0)):.3f}\n"
                f"CPM: ${float(item.get('cpm', 0)):.3f}\n"
            )
    
    return message
