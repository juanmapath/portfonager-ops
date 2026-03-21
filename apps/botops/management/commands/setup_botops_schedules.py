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

        self.stdout.write(self.style.SUCCESS(f'Processed {active_bots.count()} active bots.'))
