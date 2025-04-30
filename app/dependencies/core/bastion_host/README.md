# Connecting to Staging RDS via Bastion Host

## Prerequisites
- SSH private key: `staging-bastion-host-key-pair.pem`
- Bastion Host Public IP: `3.133.158.153`
- RDS Endpoint: `chartwise-database-instance-staging.cx44ewmqqt62.us-east-2.rds.amazonaws.com`

## SSH Tunnel Command

```
ssh -i staging-bastion-host-key-pair.pem -N -L 5433:chartwise-database-instance-staging.cx44ewmqqt62.us-east-2.rds.amazonaws.com:5432 ec2-user@3.133.158.153
```

## Connection in TablePlus
Host: 127.0.0.1
Port: 5433
User: your RDS database user
Password: your RDS password
Database: your RDS database name
