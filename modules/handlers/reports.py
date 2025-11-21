(venv) root@vm2511041557:~/FinAdvisor_AI_bot# git pull
sudo systemctl restart finadvisorbot
sudo journalctl -u finadvisorbot -f
remote: Enumerating objects: 9, done.
remote: Counting objects: 100% (9/9), done.
remote: Compressing objects: 100% (5/5), done.
remote: Total 5 (delta 4), reused 0 (delta 0), pack-reused 0 (from 0)
Unpacking objects: 100% (5/5), 1.91 KiB | 115.00 KiB/s, done.
From https://github.com/Azamat-Kerimov/FinAdvisor_AI_bot
   250afea..5d0c4d3  main       -> origin/main
Updating 250afea..5d0c4d3
Fast-forward
 modules/handlers/assets.py | 93 ++++++++++++++++++++++++++++++++++++----------------
 1 file changed, 65 insertions(+), 28 deletions(-)
Nov 21 12:59:56 vm2511041557 systemd[1]: finadvisorbot.service: Consumed 3.762s CPU time.
Nov 21 12:59:56 vm2511041557 systemd[1]: finadvisorbot.service: Scheduled restart job, restart counter is at 44.
Nov 21 12:59:56 vm2511041557 systemd[1]: Stopped FinAdvisor Telegram Bot.
Nov 21 12:59:56 vm2511041557 systemd[1]: finadvisorbot.service: Consumed 3.762s CPU time.
Nov 21 12:59:56 vm2511041557 systemd[1]: Started FinAdvisor Telegram Bot.
Nov 21 12:59:57 vm2511041557 systemd[1]: Stopping FinAdvisor Telegram Bot...
Nov 21 12:59:57 vm2511041557 systemd[1]: finadvisorbot.service: Deactivated successfully.
Nov 21 12:59:57 vm2511041557 systemd[1]: Stopped FinAdvisor Telegram Bot.
Nov 21 12:59:57 vm2511041557 systemd[1]: finadvisorbot.service: Consumed 1.036s CPU time.
Nov 21 12:59:57 vm2511041557 systemd[1]: Started FinAdvisor Telegram Bot.
Nov 21 13:00:01 vm2511041557 python3[139788]: Traceback (most recent call last):
Nov 21 13:00:01 vm2511041557 python3[139788]:   File "/root/FinAdvisor_AI_bot/bot.py", line 15, in <module>
Nov 21 13:00:01 vm2511041557 python3[139788]:     from modules.handlers import tx as tx_mod
Nov 21 13:00:01 vm2511041557 python3[139788]:   File "/root/FinAdvisor_AI_bot/modules/handlers/__init__.py", line 4, in <module>
Nov 21 13:00:01 vm2511041557 python3[139788]:     from .reports import register_report_handlers
Nov 21 13:00:01 vm2511041557 python3[139788]: ImportError: cannot import name 'register_report_handlers' from 'modules.handlers.reports' (/root/FinAdvisor_AI_bot/modules/handlers/reports.py)
Nov 21 13:00:01 vm2511041557 systemd[1]: finadvisorbot.service: Main process exited, code=exited, status=1/FAILURE
Nov 21 13:00:01 vm2511041557 systemd[1]: finadvisorbot.service: Failed with result 'exit-code'.
Nov 21 13:00:01 vm2511041557 systemd[1]: finadvisorbot.service: Consumed 4.135s CPU time.
Nov 21 13:00:02 vm2511041557 systemd[1]: finadvisorbot.service: Scheduled restart job, restart counter is at 1.
Nov 21 13:00:02 vm2511041557 systemd[1]: Stopped FinAdvisor Telegram Bot.
Nov 21 13:00:02 vm2511041557 systemd[1]: finadvisorbot.service: Consumed 4.135s CPU time.
Nov 21 13:00:02 vm2511041557 systemd[1]: Started FinAdvisor Telegram Bot.
^C
(venv) root@vm2511041557:~/FinAdvisor_AI_bot#
