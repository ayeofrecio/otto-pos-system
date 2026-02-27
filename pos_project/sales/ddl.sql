-- =============================================================================
-- POS System — MySQL DDL
-- Generated from: pos_project/sales/models.py
-- Source: Clarion TopSpeed database tables
-- Engine : InnoDB  |  Charset: utf8mb4  |  Collation: utf8mb4_unicode_ci
--
-- Table creation order (no FK constraints yet — add after all apps are built):
--   1.  tlog          TLOG        Transaction log lines
--   2.  acct          ACCT        Daily accounting / session summary
--   3.  setup         SETUP       Terminal configuration
--   4.  temptrans     TEMPTRANS   Active in-progress cart
--   5.  users         USERS       Cashier / staff accounts
--   6.  tenders       TENDERS     Payment tender type configuration
--   7.  suspend       SUSPEND     Held / parked transactions
--   8.  posnctr       POSNCTR     Transaction number counter
--   9.  posnbr        POSNBR      Transaction number + grand totals
--  10.  openmmdd      OPENMMDD    Active login tracker
--  11.  functions     FUNCTIONS   Function-key mappings
--  12.  colors        COLORS      Color code lookup
--  13.  sizes         SIZES       Size code lookup
--  14.  items         ITEMS       Product / item master
--  15.  itemdtl       ITEMDTL     Item variant (barcode + size + color)
--  16.  itemlink      ITEMLINK    Item bundle / link relationships
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. tlog  —  TransactionLog
--    One row per transaction line item.
--    Clarion source: TLOG
-- -----------------------------------------------------------------------------
CREATE TABLE `tlog` (
    `id`                  BIGINT          NOT NULL AUTO_INCREMENT,

    -- Session identifiers
    `user_id`             VARCHAR(10)     NOT NULL DEFAULT '',         -- USERID
    `user_id2`            VARCHAR(4)      NOT NULL DEFAULT '',         -- USERID2
    `terminal_id`         VARCHAR(3)      NOT NULL DEFAULT '',         -- TERMID
    `store_id`            VARCHAR(3)      NOT NULL DEFAULT '',         -- STOREID

    -- Transaction header
    `transaction_no`      VARCHAR(8)      NOT NULL DEFAULT '',         -- TRNBR
    `transaction_date`    DATE            NOT NULL,                    -- TRDATE
    `transaction_date_r`  DATE            NULL,                        -- TRDATER (return/void date)
    `transaction_time`    VARCHAR(5)      NOT NULL DEFAULT '',         -- TRTIME
    `transaction_type`    VARCHAR(1)      NOT NULL DEFAULT '',         -- TRTYPE
    `return_code`         VARCHAR(1)      NOT NULL DEFAULT '',         -- RCODE
    `item_ref`            VARCHAR(8)      NOT NULL DEFAULT '',         -- TRREF1

    -- Item detail
    `item_code`           VARCHAR(15)     NOT NULL DEFAULT '',         -- ITEMCODE
    `item_description`    VARCHAR(25)     NOT NULL DEFAULT '',         -- IDESC
    `item_qty`            DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- IQTY
    `item_uom`            VARCHAR(6)      NOT NULL DEFAULT '',         -- IUOM
    `item_supplier`       VARCHAR(6)      NOT NULL DEFAULT '',         -- ISUPP
    `item_department`     VARCHAR(4)      NOT NULL DEFAULT '',         -- IDEPT
    `item_class`          VARCHAR(4)      NOT NULL DEFAULT '',         -- ICLASS
    `item_size`           VARCHAR(3)      NOT NULL DEFAULT '',         -- ISIZE
    `item_color`          VARCHAR(3)      NOT NULL DEFAULT '',         -- ICOLOR
    `item_type`           VARCHAR(1)      NOT NULL DEFAULT '',         -- ITYPE

    -- Pricing
    `item_cost`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- ICOST
    `item_price`          DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- IPRICE
    `item_discount`       DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- IDISC
    `discount_code`       VARCHAR(3)      NOT NULL DEFAULT '',         -- IDISCCODE
    `item_price_ext`      DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- IPRICEE

    -- Tags / flags
    `tag1`                VARCHAR(1)      NOT NULL DEFAULT '',         -- ITAG1
    `tag2`                VARCHAR(1)      NOT NULL DEFAULT '',         -- ITAG2
    `tag3`                VARCHAR(1)      NOT NULL DEFAULT '',         -- ITAG3
    `tag4`                VARCHAR(1)      NOT NULL DEFAULT '',         -- ITAG4
    `promo_tag`           VARCHAR(1)      NOT NULL DEFAULT '',         -- PTAG

    -- Service / table
    `table_id`            VARCHAR(3)      NOT NULL DEFAULT '',         -- TABLEID
    `served_by`           VARCHAR(20)     NOT NULL DEFAULT '',         -- SERVEBY
    `customer_count`      VARCHAR(10)     NOT NULL DEFAULT '',         -- CUSTCNT (STRING in Clarion)

    PRIMARY KEY (`id`),
    INDEX `tlog_trno_date`        (`transaction_no`, `transaction_date`),
    INDEX `tlog_store_term_date`  (`store_id`, `terminal_id`, `transaction_date`),
    INDEX `tlog_item_code`        (`item_code`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- 2. acct  —  AccountingSummary
--    One row per cashier session per business day per terminal.
--    Clarion source: ACCT
-- -----------------------------------------------------------------------------
CREATE TABLE `acct` (
    `id`                  BIGINT          NOT NULL AUTO_INCREMENT,

    -- Session identifiers
    `store_id`            VARCHAR(3)      NOT NULL DEFAULT '',         -- STOREID
    `terminal_id`         VARCHAR(3)      NOT NULL DEFAULT '',         -- TERMID
    `transaction_date`    DATE            NOT NULL,                    -- TRDATE
    `user_id`             VARCHAR(10)     NOT NULL DEFAULT '',         -- USERID

    -- Sales totals
    `items_sold`          DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- ISOLD
    `customer_count`      DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- CUSTCNT

    -- Returns
    `return_count`        DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- IRETCNT
    `return_total`        DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- IRETTOT

    -- Void (item level)
    `void_item_count`     DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- IVOIDCNT
    `void_item_total`     DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- IVOIDTOT

    -- Void (previous transaction)
    `void_prev_count`     DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- TRVPRVCNT
    `void_prev_total`     DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- TRVPRVTOT

    -- Void (transaction level)
    `void_trans_count`    DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- TRVOIDCNT
    `void_trans_total`    DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- TRVOIDTOT

    -- Item discounts
    `item_disc_count`     DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- IDISCCNT
    `item_disc_total`     DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- IDISCTOT
    `item_disc_a_count`   DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- IDISCACNT
    `item_disc_a_total`   DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- IDISCATOT

    -- Transaction discounts
    `trans_disc_count`    DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- TDISCCNT
    `trans_disc_total`    DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- TDISCTOT
    `trans_disc_a_count`  DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- TDISCACNT
    `trans_disc_a_total`  DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- TDISCATOT

    -- Cash withdrawals / payouts
    `withdrawal_count`    DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- WITHDCNT
    `withdrawal_total`    DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- WITHDTOT

    -- Transaction range
    `first_trans_no`      VARCHAR(8)      NOT NULL DEFAULT '',         -- FTRNBR
    `last_trans_no`       VARCHAR(8)      NOT NULL DEFAULT '',         -- LTRNBR

    -- X/Z readings and running grand totals
    `x_reading`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- XREADING
    `z_reading`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- ZREADING
    `old_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- OLDTOTAL
    `new_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- NEWTOTAL

    -- Payment type buckets P01–P24
    `p01_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P01CNT
    `p01_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P01TTL
    `p02_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P02CNT
    `p02_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P02TTL
    `p03_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P03CNT
    `p03_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P03TTL
    `p04_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P04CNT
    `p04_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P04TTL
    `p05_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P05CNT
    `p05_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P05TTL
    `p06_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P06CNT
    `p06_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P06TTL
    `p07_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P07CNT
    `p07_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P07TTL
    `p08_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P08CNT
    `p08_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P08TTL
    `p09_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P09CNT
    `p09_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P09TTL
    `p10_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P10CNT
    `p10_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P10TTL
    `p11_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P11CNT
    `p11_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P11TTL
    `p12_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P12CNT
    `p12_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P12TTL
    `p13_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P13CNT
    `p13_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P13TTL
    `p14_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P14CNT
    `p14_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P14TTL
    `p15_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P15CNT
    `p15_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P15TTL
    `p16_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P16CNT
    `p16_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P16TTL
    `p17_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P17CNT
    `p17_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P17TTL
    `p18_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P18CNT
    `p18_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P18TTL
    `p19_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P19CNT
    `p19_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P19TTL
    `p20_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P20CNT
    `p20_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P20TTL
    `p21_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P21CNT
    `p21_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P21TTL
    `p22_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P22CNT
    `p22_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P22TTL
    `p23_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P23CNT
    `p23_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P23TTL
    `p24_count`           DECIMAL(10,2)   NOT NULL DEFAULT 0,          -- P24CNT
    `p24_total`           DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- P24TTL

    -- VAT breakdown
    `non_vat`             DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- NONVAT
    `vatable`             DECIMAL(15,4)   NOT NULL DEFAULT 0,          -- VATABLE

    PRIMARY KEY (`id`),
    UNIQUE KEY `acct_session_unique` (`store_id`, `terminal_id`, `transaction_date`, `user_id`),
    INDEX `acct_store_term_date`   (`store_id`, `terminal_id`, `transaction_date`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- 3. setup  —  TerminalSetup
--    One row per store/terminal. Receipt layout, port config, VAT rate.
--    Clarion source: SETUP
-- -----------------------------------------------------------------------------
CREATE TABLE `setup` (
    `id`              BIGINT          NOT NULL AUTO_INCREMENT,

    `store_id`        VARCHAR(3)      NOT NULL DEFAULT '',             -- STOREID
    `terminal_id`     VARCHAR(3)      NOT NULL DEFAULT '',             -- TERMID

    -- Receipt header lines
    `header01`        VARCHAR(40)     NOT NULL DEFAULT '',             -- HEADER01
    `header02`        VARCHAR(40)     NOT NULL DEFAULT '',             -- HEADER02
    `header03`        VARCHAR(40)     NOT NULL DEFAULT '',             -- HEADER03
    `header04`        VARCHAR(40)     NOT NULL DEFAULT '',             -- HEADER04
    `header05`        VARCHAR(40)     NOT NULL DEFAULT '',             -- HEADER05
    `header06`        VARCHAR(40)     NOT NULL DEFAULT '',             -- HEADER06

    -- Receipt footer lines
    `footer01`        VARCHAR(40)     NOT NULL DEFAULT '',             -- FOOTER01
    `footer02`        VARCHAR(40)     NOT NULL DEFAULT '',             -- FOOTER02
    `footer03`        VARCHAR(40)     NOT NULL DEFAULT '',             -- FOOTER03
    `footer04`        VARCHAR(40)     NOT NULL DEFAULT '',             -- FOOTER04

    -- Hardware ports
    `draw_port`       VARCHAR(4)      NOT NULL DEFAULT '',             -- DRAWPORT
    `print_port`      VARCHAR(4)      NOT NULL DEFAULT '',             -- PRINTPORT
    `disp_port`       VARCHAR(4)      NOT NULL DEFAULT '',             -- DISPPORT

    -- Pole display codes
    `pdsp_code_f1`    VARCHAR(5)      NOT NULL DEFAULT '',             -- PDSPCODEF1
    `pdsp_code_l1`    VARCHAR(2)      NOT NULL DEFAULT '',             -- PDSPCODEL1
    `pdsp_code_f2`    VARCHAR(5)      NOT NULL DEFAULT '',             -- PDSPCODEF2
    `pdsp_code_l2`    VARCHAR(2)      NOT NULL DEFAULT '',             -- PDSPCODEL2

    -- Tax
    `vat`             DECIMAL(8,4)    NOT NULL DEFAULT 0,              -- VAT

    PRIMARY KEY (`id`),
    UNIQUE KEY `setup_store_term` (`store_id`, `terminal_id`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- 4. temptrans  —  TempTransaction
--    Active in-progress cart lines for the current sale being rung.
--    Clarion source: TEMPTRANS
-- -----------------------------------------------------------------------------
CREATE TABLE `temptrans` (
    `id`                    BIGINT          NOT NULL AUTO_INCREMENT,

    -- Session identifiers
    `user_id`               VARCHAR(10)     NOT NULL DEFAULT '',       -- USERID
    `terminal_id`           VARCHAR(3)      NOT NULL DEFAULT '',       -- TERMID
    `store_id`              VARCHAR(3)      NOT NULL DEFAULT '',       -- STOREID

    -- Transaction header
    `transaction_no`        VARCHAR(8)      NOT NULL DEFAULT '',       -- TRNBR
    `transaction_date`      DATE            NULL,                      -- TRDATE
    `transaction_date_r`    DATE            NULL,                      -- TRDATER
    `transaction_time`      VARCHAR(5)      NOT NULL DEFAULT '',       -- TRTIME
    `transaction_type`      VARCHAR(1)      NOT NULL DEFAULT '',       -- TRTYPE
    `return_code`           VARCHAR(1)      NOT NULL DEFAULT '',       -- RCODE
    `item_ref`              VARCHAR(8)      NOT NULL DEFAULT '',       -- TRREF1

    -- Item detail
    `item_code`             VARCHAR(15)     NOT NULL DEFAULT '',       -- ITEMCODE
    `item_description`      VARCHAR(25)     NOT NULL DEFAULT '',       -- IDESC
    `item_qty`              DECIMAL(15,4)   NOT NULL DEFAULT 0,        -- IQTY
    `item_uom`              VARCHAR(6)      NOT NULL DEFAULT '',       -- IUOM
    `item_supplier`         VARCHAR(6)      NOT NULL DEFAULT '',       -- ISUPP
    `item_department`       VARCHAR(4)      NOT NULL DEFAULT '',       -- IDEPT
    `item_class`            VARCHAR(4)      NOT NULL DEFAULT '',       -- ICLASS
    `item_size`             VARCHAR(3)      NOT NULL DEFAULT '',       -- ISIZE
    `item_color`            VARCHAR(3)      NOT NULL DEFAULT '',       -- ICOLOR
    `item_type`             VARCHAR(1)      NOT NULL DEFAULT '',       -- ITYPE
    `item_tax_code`         VARCHAR(1)      NOT NULL DEFAULT '',       -- ITAXC
    `table_id`              VARCHAR(3)      NOT NULL DEFAULT '',       -- TABLEID

    -- Pricing
    `item_cost`             DECIMAL(15,4)   NOT NULL DEFAULT 0,        -- ICOST
    `item_price`            DECIMAL(15,4)   NOT NULL DEFAULT 0,        -- IPRICE
    `item_discount`         DECIMAL(15,4)   NOT NULL DEFAULT 0,        -- IDISC
    `discount_code`         VARCHAR(3)      NOT NULL DEFAULT '',       -- IDISCCODE
    `item_price_ext`        DECIMAL(15,4)   NOT NULL DEFAULT 0,        -- IPRICEE
    `old_price`             DECIMAL(15,4)   NOT NULL DEFAULT 0,        -- OLDPRICE
    `price_override`        VARCHAR(3)      NOT NULL DEFAULT '',       -- PRICEOVER

    -- Tags / flags
    `tag1`                  VARCHAR(1)      NOT NULL DEFAULT '',       -- ITAG1
    `tag2`                  VARCHAR(1)      NOT NULL DEFAULT '',       -- ITAG2
    `tag3`                  VARCHAR(1)      NOT NULL DEFAULT '',       -- ITAG3
    `tag4`                  VARCHAR(1)      NOT NULL DEFAULT '',       -- ITAG4
    `promo_tag`             VARCHAR(1)      NOT NULL DEFAULT '',       -- PTAG
    `tag`                   VARCHAR(1)      NOT NULL DEFAULT '',       -- TAG

    -- Row tracking
    `transaction_no_ctr`    VARCHAR(8)      NOT NULL DEFAULT '',       -- TRNBRCTR
    `transaction_no_ctr2`   VARCHAR(8)      NOT NULL DEFAULT '',       -- TRNBRCTR_
    `rec_ctr`               DECIMAL(15,4)   NOT NULL DEFAULT 0,        -- RECCTR
    `rec_num`               VARCHAR(256)    NOT NULL DEFAULT '',       -- RECNUM

    PRIMARY KEY (`id`),
    INDEX `temptrans_rec_ctr`   (`rec_ctr`),
    INDEX `temptrans_item_code` (`item_code`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- 5. users  —  ClarionUser
--    Cashier and back-office staff accounts.
--    Clarion source: USERS
-- -----------------------------------------------------------------------------
CREATE TABLE `users` (
    `id`               BIGINT              NOT NULL AUTO_INCREMENT,

    `user_id`          VARCHAR(10)         NOT NULL DEFAULT '',        -- UserID
    `first_name`       VARCHAR(15)         NOT NULL DEFAULT '',        -- Firstname
    `last_name`        VARCHAR(15)         NOT NULL DEFAULT '',        -- Lastname
    `middle_initial`   VARCHAR(1)          NOT NULL DEFAULT '',        -- MiddleInitial
    `suffix`           VARCHAR(6)          NOT NULL DEFAULT '',        -- Suffix
    `long_name`        VARCHAR(35)         NOT NULL DEFAULT '',        -- LongName

    -- Role / access
    `user_level`       SMALLINT UNSIGNED   NOT NULL DEFAULT 0,         -- UserLevel  (BYTE)
    `user_group`       VARCHAR(15)         NOT NULL DEFAULT '',        -- UserGroup
    `department`       VARCHAR(15)         NOT NULL DEFAULT '',        -- Department
    `modules`          VARCHAR(50)         NOT NULL DEFAULT '',        -- Modules
    `mode`             VARCHAR(1)          NOT NULL DEFAULT '',        -- Mode

    -- Credentials
    `password1`        VARCHAR(10)         NOT NULL DEFAULT '',        -- Password1
    `password2`        VARCHAR(10)         NOT NULL DEFAULT '',        -- Password2

    -- Flags
    `allow_change`     SMALLINT UNSIGNED   NOT NULL DEFAULT 0,         -- AllowChange (BYTE)
    `allow_all`        SMALLINT UNSIGNED   NOT NULL DEFAULT 0,         -- AllowAll    (BYTE)
    `active`           SMALLINT UNSIGNED   NOT NULL DEFAULT 0,         -- Active      (BYTE)
    `suspended`        SMALLINT UNSIGNED   NOT NULL DEFAULT 0,         -- Suspended   (BYTE)

    -- Expiry
    `expiry`           SMALLINT UNSIGNED   NOT NULL DEFAULT 0,         -- Expiry      (BYTE)
    `expiry_date`      DATE                NULL,                       -- ExpiryDate
    `login_days`       SMALLINT UNSIGNED   NOT NULL DEFAULT 0,         -- LoginDays   (BYTE)

    -- Schedule
    `allowed_days`     VARCHAR(8)          NOT NULL DEFAULT '',        -- AllowedDays
    `allowed_shifts`   VARCHAR(8)          NOT NULL DEFAULT '',        -- AllowedShifts

    -- Last login
    `last_login_date`  DATE                NULL,                       -- LastLogin
    `last_logon_time`  TIME                NULL,                       -- LastLogonTime

    -- Notes
    `notes`            SMALLINT            NOT NULL DEFAULT 0,         -- Notes (SHORT)
    `tag`              VARCHAR(1)          NOT NULL DEFAULT '',        -- Tag

    -- Audit
    `entry_by`         VARCHAR(10)         NOT NULL DEFAULT '',        -- EntryBy
    `entry_date`       DATE                NULL,                       -- EntryDate
    `entry_time`       TIME                NULL,                       -- EntryTime
    `update_by`        VARCHAR(10)         NOT NULL DEFAULT '',        -- UpdateBy
    `update_date`      DATE                NULL,                       -- UpdateDate
    `update_time`      TIME                NULL,                       -- UpdateTime

    PRIMARY KEY (`id`),
    UNIQUE KEY `users_user_id` (`user_id`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- 6. tenders  —  Tender
--    Payment tender type configuration. Maps to P01–P24 in acct.
--    Clarion source: TENDERS
-- -----------------------------------------------------------------------------
CREATE TABLE `tenders` (
    `id`          BIGINT          NOT NULL AUTO_INCREMENT,

    `pcode`       VARCHAR(3)      NOT NULL DEFAULT '',                 -- PCODE
    `key_name`    VARCHAR(6)      NOT NULL DEFAULT '',                 -- KEYNAME
    `description` VARCHAR(15)     NOT NULL DEFAULT '',                 -- PDESC

    -- Behaviour flags
    `pallow`      VARCHAR(1)      NOT NULL DEFAULT '',                 -- PALLOW
    `pfrank`      VARCHAR(1)      NOT NULL DEFAULT '',                 -- PFRANK
    `pbal`        VARCHAR(1)      NOT NULL DEFAULT '',                 -- PBAL
    `pacct`       VARCHAR(1)      NOT NULL DEFAULT '',                 -- PACCT
    `pdocment`    VARCHAR(1)      NOT NULL DEFAULT '',                 -- PDOCMENT
    `pchange`     VARCHAR(1)      NOT NULL DEFAULT '',                 -- PCHANGE
    `pmarkup`     VARCHAR(1)      NOT NULL DEFAULT '',                 -- PMARKUP
    `pmarkamt`    DECIMAL(12,4)   NOT NULL DEFAULT 0,                  -- PMARKAMT
    `pexpiry`     VARCHAR(1)      NOT NULL DEFAULT '',                 -- PEXPIRY
    `pcharge`     VARCHAR(1)      NOT NULL DEFAULT '',                 -- PCHARGE
    `pconvert`    VARCHAR(1)      NOT NULL DEFAULT '',                 -- PCONVERT

    -- Keyboard shortcuts
    `keychar1`    VARCHAR(1)      NOT NULL DEFAULT '',                 -- KEYCHAR1
    `keychar2`    VARCHAR(1)      NOT NULL DEFAULT '',                 -- KEYCHAR2
    `keychar3`    VARCHAR(1)      NOT NULL DEFAULT '',                 -- KEYCHAR3
    `keychar4`    VARCHAR(1)      NOT NULL DEFAULT '',                 -- KEYCHAR4

    PRIMARY KEY (`id`),
    UNIQUE KEY `tenders_pcode` (`pcode`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- 7. suspend  —  SuspendedTransaction
--    Cart lines for held / parked transactions.
--    Clarion source: SUSPEND
-- -----------------------------------------------------------------------------
CREATE TABLE `suspend` (
    `id`                    BIGINT              NOT NULL AUTO_INCREMENT,

    -- Session identifiers
    `user_id`               VARCHAR(10)         NOT NULL DEFAULT '',   -- USERID
    `user_id2`              VARCHAR(4)          NOT NULL DEFAULT '',   -- USERID2
    `terminal_id`           VARCHAR(3)          NOT NULL DEFAULT '',   -- TERMID
    `store_id`              VARCHAR(3)          NOT NULL DEFAULT '',   -- STOREID

    -- Transaction header
    `transaction_no`        VARCHAR(8)          NOT NULL DEFAULT '',   -- TRNBR
    `transaction_date`      DATE                NULL,                  -- TRDATE
    `transaction_date_r`    DATE                NULL,                  -- TRDATER
    `transaction_time`      VARCHAR(5)          NOT NULL DEFAULT '',   -- TRTIME
    `transaction_type`      VARCHAR(1)          NOT NULL DEFAULT '',   -- TRTYPE
    `return_code`           VARCHAR(1)          NOT NULL DEFAULT '',   -- RCODE
    `item_ref`              VARCHAR(8)          NOT NULL DEFAULT '',   -- TRREF1

    -- Item detail
    `item_code`             VARCHAR(15)         NOT NULL DEFAULT '',   -- ITEMCODE
    `item_description`      VARCHAR(25)         NOT NULL DEFAULT '',   -- IDESC
    `item_qty`              DECIMAL(15,4)       NOT NULL DEFAULT 0,    -- IQTY
    `item_uom`              VARCHAR(6)          NOT NULL DEFAULT '',   -- IUOM
    `item_supplier`         VARCHAR(6)          NOT NULL DEFAULT '',   -- ISUPP
    `item_department`       VARCHAR(4)          NOT NULL DEFAULT '',   -- IDEPT
    `item_class`            VARCHAR(4)          NOT NULL DEFAULT '',   -- ICLASS
    `item_size`             VARCHAR(3)          NOT NULL DEFAULT '',   -- ISIZE
    `item_color`            VARCHAR(3)          NOT NULL DEFAULT '',   -- ICOLOR
    `item_type`             VARCHAR(1)          NOT NULL DEFAULT '',   -- ITYPE
    `item_tax_code`         VARCHAR(1)          NOT NULL DEFAULT '',   -- ITAXC
    `table_id`              VARCHAR(3)          NOT NULL DEFAULT '',   -- TABLEID

    -- Pricing
    `item_cost`             DECIMAL(15,4)       NOT NULL DEFAULT 0,    -- ICOST
    `item_price`            DECIMAL(15,4)       NOT NULL DEFAULT 0,    -- IPRICE
    `item_discount`         DECIMAL(15,4)       NOT NULL DEFAULT 0,    -- IDISC
    `discount_code`         VARCHAR(3)          NOT NULL DEFAULT '',   -- IDISCCODE
    `item_price_ext`        DECIMAL(15,4)       NOT NULL DEFAULT 0,    -- IPRICEE
    `old_price`             DECIMAL(15,4)       NOT NULL DEFAULT 0,    -- OLDPRICE
    `price_override`        VARCHAR(3)          NOT NULL DEFAULT '',   -- PRICEOVER

    -- Tags / flags
    `tag1`                  VARCHAR(1)          NOT NULL DEFAULT '',   -- ITAG1
    `tag2`                  VARCHAR(1)          NOT NULL DEFAULT '',   -- ITAG2
    `tag3`                  VARCHAR(1)          NOT NULL DEFAULT '',   -- ITAG3
    `tag4`                  VARCHAR(1)          NOT NULL DEFAULT '',   -- ITAG4
    `promo_tag`             VARCHAR(1)          NOT NULL DEFAULT '',   -- PTAG
    `tag`                   VARCHAR(1)          NOT NULL DEFAULT '',   -- TAG

    -- Row / suspend tracking
    `transaction_no_ctr`    VARCHAR(8)          NOT NULL DEFAULT '',   -- TRNBRCTR
    `transaction_no_ctr2`   VARCHAR(8)          NOT NULL DEFAULT '',   -- TRNBRCTR_
    `rec_ctr`               DECIMAL(15,4)       NOT NULL DEFAULT 0,    -- RECCTR
    `rec_num`               VARCHAR(256)        NOT NULL DEFAULT '',   -- RECNUM

    -- Service
    `customer_count`        SMALLINT UNSIGNED   NOT NULL DEFAULT 0,    -- CUSTCNT (BYTE)
    `served_by`             VARCHAR(20)         NOT NULL DEFAULT '',   -- SERVEBY

    PRIMARY KEY (`id`),
    INDEX `suspend_table_id`        (`table_id`),
    INDEX `suspend_trno_recctr`     (`transaction_no`, `rec_ctr`),
    INDEX `suspend_item_code`       (`item_code`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- 8. posnctr  —  POSTransCounter
--    Single-row table holding the last-used transaction number string.
--    Clarion source: POSNCTR
-- -----------------------------------------------------------------------------
CREATE TABLE `posnctr` (
    `id`              BIGINT      NOT NULL AUTO_INCREMENT,
    `transaction_no`  VARCHAR(8)  NOT NULL DEFAULT '',                 -- TRNBR

    PRIMARY KEY (`id`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- 9. posnbr  —  POSTransNumber
--    Transaction number with running grand totals and session counters.
--    Clarion source: POSNBR
-- -----------------------------------------------------------------------------
CREATE TABLE `posnbr` (
    `id`              BIGINT          NOT NULL AUTO_INCREMENT,
    `transaction_no`  VARCHAR(8)      NOT NULL DEFAULT '',             -- TRNBR
    `grand_tot`       DECIMAL(15,4)   NOT NULL DEFAULT 0,              -- GRANDTOT
    `grand_tot2`      DECIMAL(15,4)   NOT NULL DEFAULT 0,              -- GRANDTOT2
    `prev_ctr`        DECIMAL(15,4)   NOT NULL DEFAULT 0,              -- PREVCTR
    `curr_ctr`        DECIMAL(15,4)   NOT NULL DEFAULT 0,              -- CURRCTR

    PRIMARY KEY (`id`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- 10. openmmdd  —  OpenTerminal
--     Active login tracker: which cashier is logged in on which terminal.
--     Clarion source: OPENMMDD
-- -----------------------------------------------------------------------------
CREATE TABLE `openmmdd` (
    `id`          BIGINT      NOT NULL AUTO_INCREMENT,
    `store_id`    VARCHAR(3)  NOT NULL DEFAULT '',                     -- STOREID
    `terminal_id` VARCHAR(3)  NOT NULL DEFAULT '',                     -- TERMID
    `tag`         VARCHAR(1)  NOT NULL DEFAULT '',                     -- TAG
    `user_id`     VARCHAR(10) NOT NULL DEFAULT '',                     -- USERID

    PRIMARY KEY (`id`),
    INDEX `openmmdd_user_id` (`user_id`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- 11. functions  —  POSFunction
--     Function-key / hotkey code mappings.
--     Clarion source: FUNCTIONS
-- -----------------------------------------------------------------------------
CREATE TABLE `functions` (
    `id`        BIGINT      NOT NULL AUTO_INCREMENT,
    `code`      VARCHAR(10) NOT NULL DEFAULT '',                       -- CODE
    `desc`      VARCHAR(30) NOT NULL DEFAULT '',                       -- DESC
    `key_code`  VARCHAR(2)  NOT NULL DEFAULT '',                       -- KEYCODE

    PRIMARY KEY (`id`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- 12. colors  —  Color
--     Color code lookup table for item variants.
--     Clarion source: COLORS
-- -----------------------------------------------------------------------------
CREATE TABLE `colors` (
    `id`        BIGINT          NOT NULL AUTO_INCREMENT,
    `code`      VARCHAR(5)      NOT NULL DEFAULT '',                   -- CODE
    `color`     VARCHAR(15)     NOT NULL DEFAULT '',                   -- COLOR
    `set_value` DECIMAL(10,4)   NOT NULL DEFAULT 0,                    -- SETVALUE
    `multi`     VARCHAR(15)     NOT NULL DEFAULT '',                   -- MULTI

    PRIMARY KEY (`id`),
    UNIQUE KEY `colors_code`  (`code`),
    INDEX       `colors_color` (`color`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- 13. sizes  —  Size
--     Size code lookup table for item variants.
--     Clarion source: SIZES
-- -----------------------------------------------------------------------------
CREATE TABLE `sizes` (
    `id`        BIGINT          NOT NULL AUTO_INCREMENT,
    `code`      VARCHAR(3)      NOT NULL DEFAULT '',                   -- CODE
    `size`      VARCHAR(4)      NOT NULL DEFAULT '',                   -- SIZE
    `set_value` DECIMAL(10,4)   NOT NULL DEFAULT 0,                    -- SETVALUE

    PRIMARY KEY (`id`),
    UNIQUE KEY `sizes_code` (`code`),
    INDEX       `sizes_size` (`size`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- 14. items  —  Item
--     Product / item master. One row per base SKU.
--     Clarion source: ITEMS
-- -----------------------------------------------------------------------------
CREATE TABLE `items` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT,

    -- Codes
    `icode`         VARCHAR(15)     NOT NULL DEFAULT '',               -- ICODE
    `icode2`        VARCHAR(15)     NOT NULL DEFAULT '',               -- ICODE2
    `icode3`        VARCHAR(15)     NOT NULL DEFAULT '',               -- ICODE3

    -- Description
    `long_desc`     VARCHAR(50)     NOT NULL DEFAULT '',               -- LDESC
    `short_desc`    VARCHAR(25)     NOT NULL DEFAULT '',               -- IDESC

    -- Classification
    `department`    VARCHAR(4)      NOT NULL DEFAULT '',               -- IDEPT
    `item_class`    VARCHAR(4)      NOT NULL DEFAULT '',               -- ICLASS
    `category`      VARCHAR(4)      NOT NULL DEFAULT '',               -- ICAT
    `sub_category`  VARCHAR(4)      NOT NULL DEFAULT '',               -- ISUBCAT
    `style`         VARCHAR(12)     NOT NULL DEFAULT '',               -- ISTYLE
    `color`         VARCHAR(3)      NOT NULL DEFAULT '',               -- ICOLOR
    `size`          VARCHAR(3)      NOT NULL DEFAULT '',               -- ISIZE
    `item_type`     VARCHAR(1)      NOT NULL DEFAULT '',               -- ITYPE
    `price_type`    VARCHAR(1)      NOT NULL DEFAULT '',               -- IPTYPE
    `tax_code`      VARCHAR(1)      NOT NULL DEFAULT '',               -- ITAXC
    `bar_type`      VARCHAR(1)      NOT NULL DEFAULT '',               -- IBARTYPE

    -- Pricing
    `price`         DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- IPRICE
    `price2`        DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- IPRICE2
    `price3`        DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- IPRICE3
    `price4`        DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- IPRICE4
    `cost`          DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- ICOST
    `in_cost`       DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- INCOST
    `tax_rate`      DECIMAL(10,4)   NOT NULL DEFAULT 0,                -- IRATE
    `tax_rate3`     DECIMAL(10,4)   NOT NULL DEFAULT 0,                -- IRATE3

    -- Discounts
    `disc1`         DECIMAL(10,4)   NOT NULL DEFAULT 0,                -- IDISC1
    `disc2`         DECIMAL(10,4)   NOT NULL DEFAULT 0,                -- IDISC2
    `disc3`         DECIMAL(10,4)   NOT NULL DEFAULT 0,                -- IDISC3
    `disc4`         DECIMAL(10,4)   NOT NULL DEFAULT 0,                -- IDISC4
    `disc5`         DECIMAL(10,4)   NOT NULL DEFAULT 0,                -- IDISC5
    `disc6`         DECIMAL(10,4)   NOT NULL DEFAULT 0,                -- IDISC6
    `disc_amt`      DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- IDISCAMT
    `charges`       DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- ICHARGES
    `markdown`      DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- IMARKDOWN
    `shrink`        DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- ISHRINK
    `addon`         DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- ADDON
    `add_amt`       DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- IADDAMT

    -- Promo
    `promo`         VARCHAR(1)      NOT NULL DEFAULT '',               -- IPROMO
    `promo_date1`   DATE            NULL,                              -- IPDATE1
    `promo_time1`   VARCHAR(5)      NOT NULL DEFAULT '',               -- IPTIME1
    `promo_date2`   DATE            NULL,                              -- IPDATE2
    `promo_time2`   VARCHAR(5)      NOT NULL DEFAULT '',               -- IPTIME2

    -- Unit of measure / packing (primary)
    `uom`           VARCHAR(6)      NOT NULL DEFAULT '',               -- IUOM
    `pack`          VARCHAR(7)      NOT NULL DEFAULT '',               -- IPACK
    `qty`           DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- IQTY

    -- Unit of measure / packing (secondary)
    `uom2`          VARCHAR(6)      NOT NULL DEFAULT '',               -- IUOM2
    `pack2`         VARCHAR(7)      NOT NULL DEFAULT '',               -- IPACK2
    `qty2`          DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- IQTY2

    -- Supplier / ordering
    `supplier`      VARCHAR(6)      NOT NULL DEFAULT '',               -- ISUPP
    `min_order`     DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- IMINORDER
    `po_qty`        DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- IPOQTY
    `last_order`    DATE            NULL,                              -- LORDER
    `po_no`         VARCHAR(8)      NOT NULL DEFAULT '',               -- PONO

    -- Stock
    `has_inventory` VARCHAR(1)      NOT NULL DEFAULT '',               -- IINVENT
    `stocks`        DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- ISTOCKS
    `stocks2`       DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- ISTOCKS2
    `qty_min`       DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- IQMIN
    `qty_max`       DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- IQMAX
    `warehouse_qty` DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- IWQTY
    `beg_bal1`      DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- BEGBAL1
    `beg_bal2`      DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- BEGBAL2
    `beg_cost`      DECIMAL(15,4)   NOT NULL DEFAULT 0,                -- BEGCOST
    `last_sold`     DATE            NULL,                              -- LSOLD

    -- Flags
    `inactive`      VARCHAR(1)      NOT NULL DEFAULT '',               -- INACTIVE
    `is_serial`     VARCHAR(1)      NOT NULL DEFAULT '',               -- ISERIAL
    `is_generic`    VARCHAR(1)      NOT NULL DEFAULT '',               -- IGENERIC
    `is_alias`      VARCHAR(1)      NOT NULL DEFAULT '',               -- IALIAS
    `tag`           VARCHAR(1)      NOT NULL DEFAULT '',               -- ITAG

    -- Accounting
    `gl_code`       VARCHAR(4)      NOT NULL DEFAULT '',               -- GLCODE
    `inv_code`      VARCHAR(4)      NOT NULL DEFAULT '',               -- INVCODE

    -- Audit
    `date_created`  DATE            NULL,                              -- DCREATED

    PRIMARY KEY (`id`),
    UNIQUE KEY `items_icode`      (`icode`),
    INDEX       `items_long_desc`  (`long_desc`),
    INDEX       `items_short_desc` (`short_desc`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- 15. itemdtl  —  ItemDetail
--     Item variant: one row per icode + color + size combination.
--     Barcode is the natural primary key.
--     Clarion source: ITEMDTL
-- -----------------------------------------------------------------------------
CREATE TABLE `itemdtl` (
    `id`       BIGINT          NOT NULL AUTO_INCREMENT,
    `icode`    VARCHAR(15)     NOT NULL DEFAULT '',                    -- ICODE
    `color`    VARCHAR(3)      NOT NULL DEFAULT '',                    -- COLOR
    `size`     VARCHAR(3)      NOT NULL DEFAULT '',                    -- SIZE
    `stocks1`  DECIMAL(15,4)   NOT NULL DEFAULT 0,                     -- ISTOCKS1
    `stocks2`  DECIMAL(15,4)   NOT NULL DEFAULT 0,                     -- ISTOCKS2
    `cost`     DECIMAL(15,4)   NOT NULL DEFAULT 0,                     -- ICOST
    `price`    DECIMAL(15,4)   NOT NULL DEFAULT 0,                     -- IPRICE
    `min_qty`  DECIMAL(15,4)   NOT NULL DEFAULT 0,                     -- MIN
    `max_qty`  DECIMAL(15,4)   NOT NULL DEFAULT 0,                     -- MAX
    `barcode`  VARCHAR(15)     NOT NULL DEFAULT '',                    -- BARCODE
    `multi`    VARCHAR(15)     NOT NULL DEFAULT '',                    -- MULTI

    PRIMARY KEY (`id`),
    UNIQUE KEY `itemdtl_barcode`        (`barcode`),
    INDEX       `itemdtl_icode`         (`icode`),
    INDEX       `itemdtl_icode_color`   (`icode`, `color`),
    INDEX       `itemdtl_icode_size`    (`icode`, `size`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- 16. itemlink  —  ItemLink
--     Bundle / linked item relationships. Composite key: (icode, link_code).
--     Clarion source: ITEMLINK
-- -----------------------------------------------------------------------------
CREATE TABLE `itemlink` (
    `id`        BIGINT          NOT NULL AUTO_INCREMENT,
    `icode`     VARCHAR(15)     NOT NULL DEFAULT '',                   -- ICODE
    `link_code` VARCHAR(15)     NOT NULL DEFAULT '',                   -- LINKCODE
    `desc`      VARCHAR(25)     NOT NULL DEFAULT '',                   -- IDESC
    `price`     DECIMAL(15,4)   NOT NULL DEFAULT 0,                    -- IPRICE
    `price2`    DECIMAL(15,4)   NOT NULL DEFAULT 0,                    -- IPRICE2

    PRIMARY KEY (`id`),
    UNIQUE KEY `itemlink_icode_linkcode` (`icode`, `link_code`),
    INDEX       `itemlink_icode`         (`icode`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
