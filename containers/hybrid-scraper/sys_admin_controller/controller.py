import argparse
import subprocess
import os

def setup_arguments():
    parser = argparse.ArgumentParser(description='Controller for managing cronjob processes')

    parser.add_argument('action', choices=['add', 'stop', 'edit', 'list'], help='Action to perform on cronjob processes')
    
    parser.add_argument('-m', '--minutes', type=int, help='Time in seconds')
    parser.add_argument('-H', '--hours', type=int, help='Time in hours')
    parser.add_argument('-d', '--days', type=int, help='Time in days')
    parser.add_argument('-w', '--weeks', type=int, help='Time in weeks')
    parser.add_argument('-M', '--months', type=int, help='Time in months')
    parser.add_argument('-c', '--command', type=str, help='Command to run')
    
    parser.add_argument('-p', '--pid', type=int, help='Process ID to stop')
    
    
    global args
    args = parser.parse_args()

    return args

def list_cronjob_processes():
    result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
    if result.stderr:
        return result.stderr
    return result.stdout

def add_process():
    cron_line = f"{args.minutes or '*'} {args.hours or '*'} {args.days or '*'} {args.months or '*'} {args.weeks or '*'} {args.command}"
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing_cron = result.stdout if result.returncode == 0 else ""

    # Add new job
    new_cron = existing_cron + cron_line + "\n"

    # Write updated crontab
    subprocess.run(["crontab", "-"], input=new_cron, text=True)

    
def edit_cronjob():
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        print("error: no crontab exists")
        return False
    
    existing_cron = result.stdout
    lines = existing_cron.strip().split('\n')
    
    # Find matching command
    matching_line_idx = None
    for idx, line in enumerate(lines):
        if args.command in line:
            matching_line_idx = idx
            break
    
    if matching_line_idx is None:
        print(f"error: command '{args.command}' not found in crontab")
        return False
    
    # Build new cron schedule
    new_cron_schedule = f"{args.minutes or '*'} {args.hours or '*'} {args.days or '*'} {args.months or '*'} {args.weeks or '*'} {args.command}"
    lines[matching_line_idx] = new_cron_schedule
    
    # Write updated crontab
    updated_cron = '\n'.join(lines) + '\n'
    subprocess.run(["crontab", "-"], input=updated_cron, text=True)
    
    return True

def main():
    args = setup_arguments()
    if args.action == 'list':
        print(list_cronjob_processes())
    elif args.action == "add":
        if not args.command:
            print("error: -c/--command unspecified. Cannot add a cronjob with no command")
            return
        add_process()
    elif args.action == "stop":
        if not args.pid:
            print("error: -p/--pid unspecified. Cannot stop an empty cronjob")
            return
        os.kill(args.pid)
    elif args.action == "edit":
        if not args.command:
            print("error: -c/--command unspecified. Cannot edit an unspecified cronjob")
            return
        edit_cronjob()

if __name__ == "__main__":
    main()