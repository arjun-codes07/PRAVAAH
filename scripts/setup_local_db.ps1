# PRAVAAH — Local Database Setup Script
# Idempotent script for setting up PostgreSQL 18 + PostGIS locally for PRAVAAH.

$ErrorActionPreference = "Stop"

$PsqlPath = "C:\Program Files\PostgreSQL\18\bin\psql.exe"
if (-not (Test-Path $PsqlPath)) {
    # Search PATH or alternate locations
    $psqlCmd = Get-Command psql.exe -ErrorAction SilentlyContinue
    if ($psqlCmd) {
        $PsqlPath = $psqlCmd.Source
    } else {
        Write-Error "psql.exe not found at '$PsqlPath'. Please ensure PostgreSQL 18 is installed."
        exit 1
    }
}

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "PRAVAAH Local Database Setup (PostgreSQL 18)" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# Prompt for PostgreSQL superuser password securely if not already set in environment
if (-not $env:PGPASSWORD) {
    $securePassword = Read-Host -Prompt "Enter postgres superuser password" -AsSecureString
    $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    $plainSuperpass = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
    $env:PGPASSWORD = $plainSuperpass
} else {
    $plainSuperpass = $env:PGPASSWORD
}

try {
    # 1. Test superuser connection & check PostGIS extension availability
    Write-Host "`n[1/5] Checking PostgreSQL connection and PostGIS extension availability..." -ForegroundColor Yellow
    $checkPostgisSql = "SELECT name FROM pg_available_extensions WHERE name = 'postgis';"
    $postgisAvail = & $PsqlPath -h localhost -p 5432 -U postgres -d postgres -t -A -c $checkPostgisSql 2>&1

    if ($LASTEXITCODE -ne 0 -or $postgisAvail.Trim() -ne "postgis") {
        Write-Host "ERROR: PostGIS extension is NOT available in PostgreSQL 18 installation." -ForegroundColor Red
        Write-Host "Please install PostGIS via Stack Builder for PostgreSQL 18, then re-run this script." -ForegroundColor Red
        exit 1
    }
    Write-Host "PostGIS extension is available in PostgreSQL 18." -ForegroundColor Green

    # 2. Check existing .env for password or generate random 32-character alphanumeric password for pravaah_app
    Write-Host "`n[2/5] Determining password for pravaah_app role..." -ForegroundColor Yellow
    $envPath = Join-Path $PSScriptRoot "..\.env"
    $existingPassword = $null

    if (Test-Path $envPath) {
        $envLines = Get-Content $envPath
        foreach ($line in $envLines) {
            if ($line -match "^PRAVAAH_APP_PASSWORD=(.+)$") {
                $candidate = $Matches[1].Trim()
                if ($candidate -and $candidate -ne "CHANGE_ME" -and $candidate -ne "CHANGE_ME_APP") {
                    $existingPassword = $candidate
                }
            }
        }
    }

    if ($existingPassword) {
        $appPassword = $existingPassword
        Write-Host "Using password found in .env for pravaah_app role." -ForegroundColor Green
    } else {
        Write-Host "Generating random 32-character password for pravaah_app role..." -ForegroundColor Yellow
        $chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        $bytes = New-Object byte[] 32
        $rng.GetBytes($bytes)
        $appPasswordBuilder = New-Object System.Text.StringBuilder
        for ($i = 0; $i -lt 32; $i++) {
            $idx = $bytes[$i] % $chars.Length
            [void]$appPasswordBuilder.Append($chars[$idx])
        }
        $appPassword = $appPasswordBuilder.ToString()
    }

    # 3. Create or update role pravaah_app
    Write-Host "`n[3/5] Creating / updating role pravaah_app..." -ForegroundColor Yellow
    $roleExistsSql = "SELECT 1 FROM pg_roles WHERE rolname = 'pravaah_app';"
    $roleExistsRaw = & $PsqlPath -h localhost -p 5432 -U postgres -d postgres -t -A -c $roleExistsSql
    $roleExistsStr = ("$roleExistsRaw").Trim()

    if ($roleExistsStr -eq "1") {
        $alterRoleSql = "ALTER ROLE pravaah_app WITH LOGIN PASSWORD '$appPassword';"
        & $PsqlPath -h localhost -p 5432 -U postgres -d postgres -c $alterRoleSql | Out-Null
        Write-Host "Role pravaah_app password updated successfully." -ForegroundColor Green
    } else {
        $createRoleSql = "CREATE ROLE pravaah_app WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOREPLICATION PASSWORD '$appPassword';"
        & $PsqlPath -h localhost -p 5432 -U postgres -d postgres -c $createRoleSql | Out-Null
        Write-Host "Role pravaah_app created successfully." -ForegroundColor Green
    }

    # 4. Create database pravaah if not exists and enable PostGIS
    Write-Host "`n[4/5] Creating database pravaah and enabling PostGIS..." -ForegroundColor Yellow
    $dbExistsSql = "SELECT 1 FROM pg_database WHERE datname = 'pravaah';"
    $dbExistsRaw = & $PsqlPath -h localhost -p 5432 -U postgres -d postgres -t -A -c $dbExistsSql
    $dbExistsStr = ("$dbExistsRaw").Trim()

    if ($dbExistsStr -ne "1") {
        $createDbSql = "CREATE DATABASE pravaah OWNER pravaah_app;"
        & $PsqlPath -h localhost -p 5432 -U postgres -d postgres -c $createDbSql | Out-Null
        Write-Host "Database pravaah created with owner pravaah_app." -ForegroundColor Green
    } else {
        $alterDbSql = "ALTER DATABASE pravaah OWNER TO pravaah_app;"
        & $PsqlPath -h localhost -p 5432 -U postgres -d postgres -c $alterDbSql | Out-Null
        Write-Host "Database pravaah owner ensured as pravaah_app." -ForegroundColor Green
    }

    # Run CREATE EXTENSION IF NOT EXISTS postgis inside database pravaah as superuser
    $grantSql = @"
CREATE EXTENSION IF NOT EXISTS postgis;
GRANT CONNECT ON DATABASE pravaah TO pravaah_app;
GRANT USAGE ON SCHEMA public TO pravaah_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO pravaah_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO pravaah_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO pravaah_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO pravaah_app;
"@
    & $PsqlPath -h localhost -p 5432 -U postgres -d pravaah -c $grantSql | Out-Null
    Write-Host "PostGIS extension enabled & privileges granted on database pravaah." -ForegroundColor Green

    # 5. Update .env file
    Write-Host "`n[5/5] Updating .env file..." -ForegroundColor Yellow
    $envPath = Join-Path $PSScriptRoot "..\.env"
    $envExamplePath = Join-Path $PSScriptRoot "..\.env.example"

    if (-not (Test-Path $envPath)) {
        if (Test-Path $envExamplePath) {
            Copy-Item $envExamplePath $envPath
            Write-Host "Created .env from .env.example." -ForegroundColor Green
        } else {
            Write-Error ".env.example not found."
            exit 1
        }
    }

    $dbUrl = "postgresql+psycopg://pravaah_app:$appPassword@localhost:5432/pravaah"
    
    $envLines = Get-Content $envPath
    $newLines = @()
    $updatedUrl = $false
    $updatedAppPw = $false

    foreach ($line in $envLines) {
        if ($line -match "^DATABASE_URL=") {
            $newLines += "DATABASE_URL=$dbUrl"
            $updatedUrl = $true
        } elseif ($line -match "^PRAVAAH_APP_PASSWORD=") {
            $newLines += "PRAVAAH_APP_PASSWORD=$appPassword"
            $updatedAppPw = $true
        } else {
            $newLines += $line
        }
    }

    if (-not $updatedUrl) {
        $newLines += "DATABASE_URL=$dbUrl"
    }
    if (-not $updatedAppPw) {
        $newLines += "PRAVAAH_APP_PASSWORD=$appPassword"
    }

    $newLines | Set-Content -Path $envPath -Encoding utf8
    Write-Host ".env updated successfully with generated credentials (masked)." -ForegroundColor Green

    Write-Host "`nSetup completed successfully!" -ForegroundColor Cyan

} finally {
    # Always clear sensitive variables
    $env:PGPASSWORD = $null
    $plainSuperpass = $null
    $appPassword = $null
}
