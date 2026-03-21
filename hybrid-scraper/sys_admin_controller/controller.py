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
    # Get current crontab
    result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
    cron_lines = result.stdout.splitlines()
    
    # Build new cron line with correct order
    new_cron_line = f"{args.minutes or '*'} {args.hours or '*'} {args.days or '*'} {args.months or '*'} {args.weeks or '*'} {args.command}"
    
    updated_cron = []
    edited = False
    for line in cron_lines:
        # Split line to get command part
        parts = line.split()
        if len(parts) >= 6:
            command_part = ' '.join(parts[5:])
            if command_part == args.command and not edited:
                updated_cron.append(new_cron_line)
                edited = True
                continue
        updated_cron.append(line)
    
    if not edited:
        print("No matching cron job found to edit.")
    else:
        subprocess.run(['crontab', '-'], input='\n'.join(updated_cron) + '\n', text=True)
        print("Cron job edited successfully.")

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

if __name__ == "__main__":
    main()