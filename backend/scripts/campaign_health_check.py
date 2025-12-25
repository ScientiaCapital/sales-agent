#!/usr/bin/env python3
"""
Campaign Health Check Script

Queries Close CRM API for campaign metrics and displays health status.

Usage:
    python campaign_health_check.py --date 2025-12-29
    python campaign_health_check.py --date-range 2025-12-29 2026-01-05
    python campaign_health_check.py --sequence-id seq_469XPP98mPXSR2wh5cX9y6

Features:
- Delivery metrics (sent, delivered, bounced)
- Engagement metrics (opens, replies, unsubscribes)
- Health status indicators (Green/Yellow/Red)
- Daily breakdown
- Export to CSV
"""

import os
import sys
import argparse
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import settings


# ANSI color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


# Thresholds from monitoring checklist
THRESHOLDS = {
    'delivery_rate': {'green': 95, 'yellow': 90},  # Percent
    'bounce_rate': {'green': 5, 'yellow': 10},  # Percent
    'spam_rate': {'green': 0.1, 'yellow': 0.5},  # Percent
    'open_rate': {'green': 15, 'yellow': 10},  # Percent
    'reply_rate': {'green': 2, 'yellow': 1},  # Percent
    'unsubscribe_rate': {'green': 2, 'yellow': 5},  # Percent
}


def get_health_status(metric: str, value: float) -> Tuple[str, str]:
    """
    Get health status and color for a metric.

    Returns:
        Tuple of (status, color) where status is '🟢', '🟡', or '🔴'
    """
    thresholds = THRESHOLDS.get(metric, {})

    if not thresholds:
        return '⚪', Colors.END

    green_threshold = thresholds.get('green')
    yellow_threshold = thresholds.get('yellow')

    # For rates we want to be BELOW (bounce, spam, unsubscribe)
    if metric in ['bounce_rate', 'spam_rate', 'unsubscribe_rate']:
        if value <= green_threshold:
            return '🟢', Colors.GREEN
        elif value <= yellow_threshold:
            return '🟡', Colors.YELLOW
        else:
            return '🔴', Colors.RED

    # For rates we want to be ABOVE (delivery, open, reply)
    else:
        if value >= green_threshold:
            return '🟢', Colors.GREEN
        elif value >= yellow_threshold:
            return '🟡', Colors.YELLOW
        else:
            return '🔴', Colors.RED


def query_close_api(endpoint: str, params: Optional[Dict] = None) -> Dict:
    """
    Query Close CRM API.

    Args:
        endpoint: API endpoint (e.g., '/activity/email/')
        params: Query parameters

    Returns:
        API response JSON
    """
    url = f"https://api.close.com/api/v1{endpoint}"

    api_key = os.getenv('CLOSE_API_KEY')
    if not api_key:
        raise ValueError("CLOSE_API_KEY environment variable not set")

    response = requests.get(
        url,
        auth=(api_key, ''),
        params=params or {},
        timeout=30
    )

    if response.status_code != 200:
        raise Exception(f"Close API error: {response.status_code} - {response.text}")

    return response.json()


def get_email_activities(date_gte: str, date_lte: Optional[str] = None) -> List[Dict]:
    """
    Get all email activities for a date range.

    Args:
        date_gte: Start date (ISO format: 2025-12-29)
        date_lte: End date (optional)

    Returns:
        List of email activity objects
    """
    params = {
        'date_created__gte': date_gte,
        '_limit': 1000,  # Max per page
    }

    if date_lte:
        params['date_created__lte'] = date_lte

    all_activities = []
    has_more = True
    skip = 0

    while has_more:
        params['_skip'] = skip

        response = query_close_api('/activity/email/', params)

        activities = response.get('data', [])
        all_activities.extend(activities)

        has_more = response.get('has_more', False)
        skip += len(activities)

    return all_activities


def get_sequence_subscriptions(sequence_id: str) -> List[Dict]:
    """
    Get all subscriptions for a sequence.

    Args:
        sequence_id: Close sequence ID (seq_xxx)

    Returns:
        List of subscription objects
    """
    params = {
        'sequence_id': sequence_id,
        '_limit': 1000,
    }

    all_subscriptions = []
    has_more = True
    skip = 0

    while has_more:
        params['_skip'] = skip

        response = query_close_api('/sequence_subscription/', params)

        subscriptions = response.get('data', [])
        all_subscriptions.extend(subscriptions)

        has_more = response.get('has_more', False)
        skip += len(subscriptions)

    return all_subscriptions


def calculate_metrics(activities: List[Dict]) -> Dict:
    """
    Calculate campaign metrics from email activities.

    Args:
        activities: List of email activity objects from Close API

    Returns:
        Dict with calculated metrics
    """
    total_sent = 0
    total_delivered = 0
    total_bounced = 0
    total_opened = 0
    total_replied = 0
    total_spam = 0
    total_unsubscribe = 0

    for activity in activities:
        status = activity.get('status', '')

        # Count all sent emails
        if status in ['sent', 'delivered', 'opened', 'replied']:
            total_sent += 1

        # Count delivered
        if status in ['delivered', 'opened', 'replied']:
            total_delivered += 1

        # Count bounced
        if status == 'bounced':
            total_bounced += 1
            total_sent += 1  # Bounces count as sent attempts

        # Count opened
        if status in ['opened', 'replied']:
            total_opened += 1

        # Count replied
        if status == 'replied':
            total_replied += 1

        # Count spam complaints (if Close tracks this)
        if activity.get('spam_complaint', False):
            total_spam += 1

        # Count unsubscribes
        if activity.get('unsubscribe', False):
            total_unsubscribe += 1

    # Calculate rates
    delivery_rate = (total_delivered / total_sent * 100) if total_sent > 0 else 0
    bounce_rate = (total_bounced / total_sent * 100) if total_sent > 0 else 0
    spam_rate = (total_spam / total_sent * 100) if total_sent > 0 else 0
    open_rate = (total_opened / total_delivered * 100) if total_delivered > 0 else 0
    reply_rate = (total_replied / total_delivered * 100) if total_delivered > 0 else 0
    unsubscribe_rate = (total_unsubscribe / total_sent * 100) if total_sent > 0 else 0

    return {
        'total_sent': total_sent,
        'total_delivered': total_delivered,
        'total_bounced': total_bounced,
        'total_opened': total_opened,
        'total_replied': total_replied,
        'total_spam': total_spam,
        'total_unsubscribe': total_unsubscribe,
        'delivery_rate': delivery_rate,
        'bounce_rate': bounce_rate,
        'spam_rate': spam_rate,
        'open_rate': open_rate,
        'reply_rate': reply_rate,
        'unsubscribe_rate': unsubscribe_rate,
    }


def display_metrics_table(metrics: Dict, title: str = "Campaign Metrics"):
    """
    Display metrics in a formatted table with health indicators.
    """
    print(f"\n{Colors.BOLD}{title}{Colors.END}")
    print("=" * 80)

    # Delivery metrics
    print(f"\n{Colors.BOLD}📧 Delivery Performance{Colors.END}")
    print("-" * 80)

    print(f"Total Sent:        {metrics['total_sent']}")
    print(f"Total Delivered:   {metrics['total_delivered']}")
    print(f"Total Bounced:     {metrics['total_bounced']}")

    status, color = get_health_status('delivery_rate', metrics['delivery_rate'])
    print(f"Delivery Rate:     {color}{metrics['delivery_rate']:.1f}% {status}{Colors.END} (Target: >95%)")

    status, color = get_health_status('bounce_rate', metrics['bounce_rate'])
    print(f"Bounce Rate:       {color}{metrics['bounce_rate']:.1f}% {status}{Colors.END} (Target: <5%)")

    status, color = get_health_status('spam_rate', metrics['spam_rate'])
    print(f"Spam Complaints:   {color}{metrics['total_spam']} ({metrics['spam_rate']:.2f}%) {status}{Colors.END} (Target: <0.1%)")

    # Engagement metrics
    print(f"\n{Colors.BOLD}📊 Engagement Performance{Colors.END}")
    print("-" * 80)

    print(f"Total Opened:      {metrics['total_opened']}")
    print(f"Total Replied:     {metrics['total_replied']}")
    print(f"Total Unsubscribe: {metrics['total_unsubscribe']}")

    status, color = get_health_status('open_rate', metrics['open_rate'])
    print(f"Open Rate:         {color}{metrics['open_rate']:.1f}% {status}{Colors.END} (Target: 15-25%)")

    status, color = get_health_status('reply_rate', metrics['reply_rate'])
    print(f"Reply Rate:        {color}{metrics['reply_rate']:.1f}% {status}{Colors.END} (Target: 2-5%)")

    status, color = get_health_status('unsubscribe_rate', metrics['unsubscribe_rate'])
    print(f"Unsubscribe Rate:  {color}{metrics['unsubscribe_rate']:.1f}% {status}{Colors.END} (Target: <2%)")

    print("=" * 80)


def display_daily_breakdown(activities: List[Dict]):
    """
    Display daily breakdown of activities.
    """
    daily_metrics = defaultdict(lambda: {
        'sent': 0,
        'delivered': 0,
        'bounced': 0,
        'opened': 0,
        'replied': 0,
    })

    for activity in activities:
        # Parse date from created timestamp
        created = activity.get('date_created', '')
        if not created:
            continue

        date = created.split('T')[0]  # Extract date part (2025-12-29)
        status = activity.get('status', '')

        # Count by status
        if status in ['sent', 'delivered', 'opened', 'replied']:
            daily_metrics[date]['sent'] += 1
        if status in ['delivered', 'opened', 'replied']:
            daily_metrics[date]['delivered'] += 1
        if status == 'bounced':
            daily_metrics[date]['bounced'] += 1
            daily_metrics[date]['sent'] += 1
        if status in ['opened', 'replied']:
            daily_metrics[date]['opened'] += 1
        if status == 'replied':
            daily_metrics[date]['replied'] += 1

    print(f"\n{Colors.BOLD}📅 Daily Breakdown{Colors.END}")
    print("=" * 80)
    print(f"{'Date':<12} {'Sent':>8} {'Delivered':>10} {'Bounced':>8} {'Opened':>8} {'Replied':>8}")
    print("-" * 80)

    for date in sorted(daily_metrics.keys()):
        metrics = daily_metrics[date]
        print(
            f"{date:<12} "
            f"{metrics['sent']:>8} "
            f"{metrics['delivered']:>10} "
            f"{metrics['bounced']:>8} "
            f"{metrics['opened']:>8} "
            f"{metrics['replied']:>8}"
        )

    print("=" * 80)


def display_sequence_health(sequence_id: str):
    """
    Display sequence subscription health.
    """
    subscriptions = get_sequence_subscriptions(sequence_id)

    status_counts = defaultdict(int)
    for sub in subscriptions:
        status = sub.get('status', 'unknown')
        status_counts[status] += 1

    total = len(subscriptions)
    active = status_counts.get('active', 0)
    paused = status_counts.get('paused', 0)
    stopped = status_counts.get('stopped', 0)
    finished = status_counts.get('finished', 0)

    print(f"\n{Colors.BOLD}🔄 Sequence Health{Colors.END}")
    print("=" * 80)
    print(f"Sequence ID:       {sequence_id}")
    print(f"Total Subscriptions: {total}")
    print(f"Active:            {Colors.GREEN}{active}{Colors.END} ({active/total*100:.1f}%)")
    print(f"Paused:            {Colors.YELLOW}{paused}{Colors.END} ({paused/total*100:.1f}%)")
    print(f"Stopped:           {Colors.RED}{stopped}{Colors.END} ({stopped/total*100:.1f}%)")
    print(f"Finished:          {finished} ({finished/total*100:.1f}%)")
    print("=" * 80)


def export_to_csv(metrics: Dict, activities: List[Dict], filename: str):
    """
    Export metrics to CSV file.
    """
    import csv

    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)

        # Write summary metrics
        writer.writerow(['Campaign Summary'])
        writer.writerow(['Metric', 'Value', 'Rate'])
        writer.writerow(['Total Sent', metrics['total_sent'], ''])
        writer.writerow(['Total Delivered', metrics['total_delivered'], f"{metrics['delivery_rate']:.1f}%"])
        writer.writerow(['Total Bounced', metrics['total_bounced'], f"{metrics['bounce_rate']:.1f}%"])
        writer.writerow(['Total Opened', metrics['total_opened'], f"{metrics['open_rate']:.1f}%"])
        writer.writerow(['Total Replied', metrics['total_replied'], f"{metrics['reply_rate']:.1f}%"])
        writer.writerow(['Total Spam', metrics['total_spam'], f"{metrics['spam_rate']:.2f}%"])
        writer.writerow(['Total Unsubscribe', metrics['total_unsubscribe'], f"{metrics['unsubscribe_rate']:.1f}%"])
        writer.writerow([])

        # Write daily breakdown
        writer.writerow(['Daily Breakdown'])
        writer.writerow(['Date', 'Sent', 'Delivered', 'Bounced', 'Opened', 'Replied'])

        daily_metrics = defaultdict(lambda: {
            'sent': 0, 'delivered': 0, 'bounced': 0, 'opened': 0, 'replied': 0
        })

        for activity in activities:
            created = activity.get('date_created', '')
            if not created:
                continue

            date = created.split('T')[0]
            status = activity.get('status', '')

            if status in ['sent', 'delivered', 'opened', 'replied']:
                daily_metrics[date]['sent'] += 1
            if status in ['delivered', 'opened', 'replied']:
                daily_metrics[date]['delivered'] += 1
            if status == 'bounced':
                daily_metrics[date]['bounced'] += 1
                daily_metrics[date]['sent'] += 1
            if status in ['opened', 'replied']:
                daily_metrics[date]['opened'] += 1
            if status == 'replied':
                daily_metrics[date]['replied'] += 1

        for date in sorted(daily_metrics.keys()):
            m = daily_metrics[date]
            writer.writerow([
                date, m['sent'], m['delivered'], m['bounced'], m['opened'], m['replied']
            ])

    print(f"\n✅ Metrics exported to: {filename}")


def main():
    parser = argparse.ArgumentParser(
        description='Campaign Health Check - Monitor Close CRM campaign performance'
    )

    parser.add_argument(
        '--date',
        type=str,
        help='Single date to check (ISO format: 2025-12-29)'
    )

    parser.add_argument(
        '--date-range',
        nargs=2,
        metavar=('START', 'END'),
        help='Date range to check (ISO format: 2025-12-29 2026-01-05)'
    )

    parser.add_argument(
        '--sequence-id',
        type=str,
        help='Check specific sequence subscription health'
    )

    parser.add_argument(
        '--export',
        type=str,
        help='Export metrics to CSV file'
    )

    parser.add_argument(
        '--no-daily',
        action='store_true',
        help='Skip daily breakdown display'
    )

    args = parser.parse_args()

    # Determine date range
    if args.date_range:
        date_gte, date_lte = args.date_range
    elif args.date:
        date_gte = args.date
        date_lte = None
    else:
        # Default to today
        date_gte = datetime.now().strftime('%Y-%m-%d')
        date_lte = None

    print(f"\n{Colors.BOLD}Campaign Health Check{Colors.END}")
    print(f"Date Range: {date_gte}" + (f" to {date_lte}" if date_lte else " (single day)"))

    # Fetch email activities
    print("\nFetching email activities from Close CRM...")
    activities = get_email_activities(date_gte, date_lte)
    print(f"✅ Found {len(activities)} email activities")

    # Calculate metrics
    metrics = calculate_metrics(activities)

    # Display metrics table
    title = f"Campaign Metrics ({date_gte}" + (f" to {date_lte}" if date_lte else "") + ")"
    display_metrics_table(metrics, title)

    # Display daily breakdown (unless skipped)
    if not args.no_daily and len(activities) > 0:
        display_daily_breakdown(activities)

    # Display sequence health (if requested)
    if args.sequence_id:
        display_sequence_health(args.sequence_id)

    # Export to CSV (if requested)
    if args.export:
        export_to_csv(metrics, activities, args.export)

    # Overall health assessment
    print(f"\n{Colors.BOLD}🏥 Overall Campaign Health{Colors.END}")
    print("=" * 80)

    red_flags = []
    yellow_flags = []

    # Check each metric
    for metric in ['delivery_rate', 'bounce_rate', 'spam_rate', 'open_rate', 'reply_rate', 'unsubscribe_rate']:
        status, _ = get_health_status(metric, metrics[metric])
        if status == '🔴':
            red_flags.append(metric.replace('_', ' ').title())
        elif status == '🟡':
            yellow_flags.append(metric.replace('_', ' ').title())

    if red_flags:
        print(f"{Colors.RED}🔴 RED FLAGS: {', '.join(red_flags)}{Colors.END}")
        print(f"{Colors.RED}⚠️  ACTION REQUIRED: Review escalation procedures{Colors.END}")
    elif yellow_flags:
        print(f"{Colors.YELLOW}🟡 YELLOW FLAGS: {', '.join(yellow_flags)}{Colors.END}")
        print(f"{Colors.YELLOW}⚠️  MONITOR CLOSELY: Check daily for improvement{Colors.END}")
    else:
        print(f"{Colors.GREEN}🟢 ALL SYSTEMS GREEN{Colors.END}")
        print(f"{Colors.GREEN}✅ Campaign performing within targets{Colors.END}")

    print("=" * 80)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.RED}ERROR: {e}{Colors.END}")
        sys.exit(1)
