# Migrate

I goal here is to create a way to migrate from an existing sqlite database to postgres. TDB

### Migrate sqlite database to postgres (*Doesn't work. pgloader seems to be abandoned)
```
psql: CREATE DATABASE discovarr_test_migrate;

cat <<EOF > /tmp/migrate.pgloader
load database
     from '/app/discovarr-dev/discovarr.db'
     into postgresql://admin:admin@localhost:5432/discovarr_test_migrate 
     
  set work_mem to '16MB', maintenance_work_mem to '512 MB';
EOF

sudo pgloader -vd /tmp/migrate.pgloader
```