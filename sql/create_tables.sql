-- sql/create_tables.sql
-- 建立五張正規化資料表（Users 已存在，不重建）並插入初始測試資料
-- 執行方式：sqlcmd -S localhost -E -d tree_db -i sql/create_tables.sql

-- ── 1. Sites ──────────────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Sites')
BEGIN
    CREATE TABLE Sites (
        id   INT IDENTITY(1,1) PRIMARY KEY,
        name NVARCHAR(50) NOT NULL UNIQUE
    );
    PRINT 'Sites created';
END

-- ── 2. Species_Ref ────────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Species_Ref')
BEGIN
    CREATE TABLE Species_Ref (
        id              INT IDENTITY(1,1) PRIMARY KEY,
        name            NVARCHAR(50)  NOT NULL,
        scientific_name NVARCHAR(100) NULL,
        a               FLOAT NOT NULL,
        b               FLOAT NOT NULL,
        carbon_fraction FLOAT NOT NULL DEFAULT 0.47
    );
    PRINT 'Species_Ref created';
END

-- ── 3. Trees ──────────────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Trees')
BEGIN
    CREATE TABLE Trees (
        id         INT IDENTITY(1,1) PRIMARY KEY,
        species_id INT  NOT NULL REFERENCES Species_Ref(id),
        site_id    INT  NULL     REFERENCES Sites(id),
        latitude   FLOAT NULL,
        longitude  FLOAT NULL,
        track_id   NVARCHAR(50) NULL,
        created_at DATETIME NOT NULL DEFAULT GETDATE()
    );
    PRINT 'Trees created';
END

-- ── 4. Measurements ───────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Measurements')
BEGIN
    CREATE TABLE Measurements (
        id             INT IDENTITY(1,1) PRIMARY KEY,
        tree_id        INT          NOT NULL REFERENCES Trees(id),
        dbh            FLOAT        NOT NULL,
        carbon         FLOAT        NOT NULL,
        status         NVARCHAR(20) NOT NULL DEFAULT 'pending',
        thumbnail_path NVARCHAR(255) NULL,
        recorded_at    DATETIME NOT NULL DEFAULT GETDATE()
    );
    PRINT 'Measurements created';
END

-- ── 初始 Sites ────────────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM Sites WHERE name = N'英專路')
    INSERT INTO Sites (name) VALUES (N'英專路');
IF NOT EXISTS (SELECT 1 FROM Sites WHERE name = N'學府路')
    INSERT INTO Sites (name) VALUES (N'學府路');
IF NOT EXISTS (SELECT 1 FROM Sites WHERE name = N'淡水校園')
    INSERT INTO Sites (name) VALUES (N'淡水校園');

-- ── 初始 Species_Ref（係數與 services/diameter_calc.py 一致）──────
IF NOT EXISTS (SELECT 1 FROM Species_Ref WHERE name = N'樟樹')
    INSERT INTO Species_Ref (name, scientific_name, a, b, carbon_fraction)
    VALUES (N'樟樹', N'Cinnamomum camphora', 0.1, 2.4, 0.47);
IF NOT EXISTS (SELECT 1 FROM Species_Ref WHERE name = N'榕樹')
    INSERT INTO Species_Ref (name, scientific_name, a, b, carbon_fraction)
    VALUES (N'榕樹', N'Ficus microcarpa', 0.12, 2.3, 0.47);
IF NOT EXISTS (SELECT 1 FROM Species_Ref WHERE name = N'楓香')
    INSERT INTO Species_Ref (name, scientific_name, a, b, carbon_fraction)
    VALUES (N'楓香', N'Liquidambar formosana', 0.1, 2.4, 0.47);
IF NOT EXISTS (SELECT 1 FROM Species_Ref WHERE name = N'台灣欒樹')
    INSERT INTO Species_Ref (name, scientific_name, a, b, carbon_fraction)
    VALUES (N'台灣欒樹', N'Koelreuteria elegans', 0.1, 2.4, 0.47);

-- ── 測試 Trees + Measurements（status='confirmed' 讓公開頁面能看到）
DECLARE @site1 INT, @site2 INT;
DECLARE @sp1 INT, @sp2 INT, @sp3 INT;
SELECT @site1 = id FROM Sites       WHERE name = N'英專路';
SELECT @site2 = id FROM Sites       WHERE name = N'學府路';
SELECT @sp1   = id FROM Species_Ref WHERE name = N'樟樹';
SELECT @sp2   = id FROM Species_Ref WHERE name = N'榕樹';
SELECT @sp3   = id FROM Species_Ref WHERE name = N'楓香';

DECLARE @t1 INT, @t2 INT, @t3 INT, @t4 INT;

INSERT INTO Trees (species_id, site_id, latitude, longitude)
VALUES (@sp1, @site1, 25.17450, 121.45021);
SET @t1 = SCOPE_IDENTITY();

INSERT INTO Trees (species_id, site_id, latitude, longitude)
VALUES (@sp2, @site1, 25.17470, 121.45035);
SET @t2 = SCOPE_IDENTITY();

INSERT INTO Trees (species_id, site_id, latitude, longitude)
VALUES (@sp3, @site2, 25.17490, 121.45060);
SET @t3 = SCOPE_IDENTITY();

INSERT INTO Trees (species_id, site_id, latitude, longitude)
VALUES (@sp1, @site2, 25.17510, 121.45080);
SET @t4 = SCOPE_IDENTITY();

INSERT INTO Measurements (tree_id, dbh, carbon, status)
VALUES (@t1, 35.5, 12.4, 'confirmed');
INSERT INTO Measurements (tree_id, dbh, carbon, status)
VALUES (@t2, 42.0, 18.7, 'confirmed');
INSERT INTO Measurements (tree_id, dbh, carbon, status)
VALUES (@t3, 28.3,  7.9, 'confirmed');
INSERT INTO Measurements (tree_id, dbh, carbon, status)
VALUES (@t4, 31.0,  9.6, 'confirmed');
-- 一筆 pending，測試後台能看到但公開頁面不顯示
INSERT INTO Measurements (tree_id, dbh, carbon, status)
VALUES (@t1, 36.0, 12.8, 'pending');

PRINT 'Seed data inserted.';
