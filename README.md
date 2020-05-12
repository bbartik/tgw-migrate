# TGW Migrate Script

## Instructions

1. Manually add the following tag to the route tables being migrated

tag = {'Key': 'migrate', 'Value': 'true'}

2. Set the TGW_ID variable:

On linux/mac:
export TGW_ID=<tgw-id>

On Windows
set TGW_ID=<tgw-id>

2. Run script to Migrate:

python tgw-migrate.py migrate

Backup files will be created in ./backups/

3. Rollback if needed with the rollback option:

python tgw-migrate.py rollback
