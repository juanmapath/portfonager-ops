from django.core.management.base import BaseCommand
from django_q.models import Schedule
from apps.botops.models import Bot

class Command(BaseCommand):
    help = 'Sets up the Django Q schedules for bot operations'

    def handle(self, *args, **kwargs):
        self.stdout.write("Setting up Django Q schedules...")

        list_of_names_od_bots=['USMarketQTN Bot Execution', 'MaxCaps Bot Execution','Speculator Bot Execution','PortIn Bot Execution','BuyDollar Bot Execution','HeavyX Bot Execution']
        # Clear old hardcoded schedules if they exist
        Schedule.objects.filter(name__in=list_of_names_od_bots).delete()

        active_bots = Bot.objects.filter(active=True)
        for bot in active_bots:
            minute = bot.execute_minute
            schedule_name = f'Bot Execution: {bot.name}'
            
            schedule, created = Schedule.objects.update_or_create(
                name=schedule_name,
                defaults={
                    'func': 'apps.botops.ops.execute_bots.run_bot',
                    'args': (bot.family.id, bot.id),
                    'schedule_type': Schedule.CRON,
                    'cron': f'{minute} * * * 1-5',  # Monday to Friday
                    'repeats': -1
                }
            )
            
            status = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f'{status} schedule for {bot.name} at minute {minute}'))

        from apps.botops.models import GeneralSettings
        try:
            settings = GeneralSettings.objects.first()
            end_hour = settings.end_hour if settings else 17
        except Exception:
            end_hour = 17

        # Add portfolio history daily schedule at end_hour, minute 0, Mon-Fri
        hist_schedule_name = 'Daily Portfolio History'
        hist_schedule, created = Schedule.objects.update_or_create(
            name=hist_schedule_name,
            defaults={
                'func': 'apps.botops.ops.history_updater.all_bots_hist',
                'schedule_type': Schedule.CRON,
                'cron': f'0 {end_hour} * * 1-5',
                'repeats': -1
            }
        )
        hist_status = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f'{hist_status} schedule for {hist_schedule_name}'))

        # Add daily finviz metrics update schedule at 19:00 (7 PM), Mon-Fri
        finviz_schedule_name = 'Daily Finviz Metrics Update'
        finviz_schedule, created = Schedule.objects.update_or_create(
            name=finviz_schedule_name,
            defaults={
                'func': 'apps.gemsfinder.funcs.update_all_finviz_metrics.run_update',
                'schedule_type': Schedule.CRON,
                'cron': '0 19 * * 1-5',
                'repeats': -1
            }
        )
        finviz_status = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f'{finviz_status} schedule for {finviz_schedule_name}'))

        # Add weekly GemsFinder screener schedule - every Friday at 10 PM
        gems_schedule_name = 'Weekly GemsFinder Screener'
        gems_schedule, created = Schedule.objects.update_or_create(
            name=gems_schedule_name,
            defaults={
                'func': 'apps.gemsfinder.funcs.run_sts.run_st',
                'schedule_type': Schedule.CRON,
                'cron': '0 22 * * 5',  # Friday at 10 PM
                'repeats': -1
            }
        )
        gems_status = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f'{gems_status} schedule for {gems_schedule_name}'))

        # Add weekly backtest schedule - every Sunday at 6 AM
        backtest_schedule_name = 'Weekly Active Bots Backtest'
        backtest_schedule, created = Schedule.objects.update_or_create(
            name=backtest_schedule_name,
            defaults={
                'func': 'apps.backtestlab.scripts.backtest_model.run_all_active_bots',
                'schedule_type': Schedule.CRON,
                'cron': '0 6 * * 0',  # Sunday at 6 AM
                'repeats': -1
            }
        )
        backtest_status = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f'{backtest_status} schedule for {backtest_schedule_name}'))

        self.stdout.write(self.style.SUCCESS(f'Processed {active_bots.count()} active bots.'))
