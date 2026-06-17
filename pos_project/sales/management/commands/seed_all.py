import os
from django.core.management.base import BaseCommand
from django.core.management import call_command

# 1. Import your CSV utility function from your views file
# (Replace 'your_app' with the actual name of your Django app folder)
from sales.views import import_products_from_csv 

# 2. Define the paths to your CSV files so the seeder can find them
# Adjust these paths to point to where your CSVs are actually stored
CSV_ITEMS_PATH      = os.environ.get("CSV_ITEMS_PATH")
CSV_ITEMDTL_PATH    = os.environ.get("CSV_ITEMDTL_PATH")
CSV_ITEMSCOSTS_PATH = os.environ.get("CSV_ITEMSCOSTS_PATH")


class Command(BaseCommand):
    help = "Runs all database seeders for the POS system in the correct order"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Starting database seeding..."))
        
        # Step 1: Basic App Settings
        # self.stdout.write("Seeding system settings...")
        # call_command('seed_settings')
        self.stdout.write("Seeding system termninal...")
        call_command('seed_terminal')
        
        # Step 2: Initialize POS Number 
        # FIX: Flags like '--start' and '--force' must be passed as keyword arguments!
        self.stdout.write("Initializing POS numbers...")
        call_command('init_posnbr', start='12345', force=True)
        
        # Step 3: Run the CSV Import function directly from your views
        self.stdout.write("Truncating tables and importing items from CSV files...")
        try:
            summary = import_products_from_csv(
                CSV_ITEMS_PATH,
                CSV_ITEMDTL_PATH,
                CSV_ITEMSCOSTS_PATH,
            )
            self.stdout.write(self.style.SUCCESS(
                f"-> CSV Import successful! Loaded {summary['items_loaded']} items, "
                f"{summary['item_details_loaded']} variants, {summary['costs_updated']} costs."
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"-> CSV Import failed: {str(e)}"))
            # Optional: Raise the error if you want the whole seeder to stop on failure
            raise e
        
        # Step 4: Seed System Functions
        self.stdout.write("Seeding system functions...")
        call_command('seed_functions')
        
        # Step 5: Seed Payment Tenders
        self.stdout.write("Seeding payment tenders...")
        call_command('seed_tenders')
        self.stdout.write("Seeding superuser...")
        call_command('seed_superuser')

        self.stdout.write(self.style.SUCCESS("🎉 All seeders executed successfully!"))