@echo off
rem Forward paper run of the frozen second-low rule. No order is sent.
rem Scheduled by Windows Task "Tradelatest_SecondLow_Live" (every 4 hours, 10 minutes after each broker H4 close).
cd /d D:\Tradelatest
echo ==== %date% %time% >> userinvestigation\second_low_algo\live_task.log
venv\Scripts\python.exe userinvestigation\second_low_algo\second_low_algo.py live --rule userinvestigation\second_low_algo\rule_frozen.json --forward-start 2026-10-07 --out-dir userinvestigation\second_low_algo >> userinvestigation\second_low_algo\live_task.log 2>&1
echo exit %errorlevel% >> userinvestigation\second_low_algo\live_task.log
