-- Planted issues, for the skill to find:
-- 1. Composite primary key (CreatedDate, Id) vs. Task.java's single-column @Id("id").
-- 2. Column naming drift: most columns are PascalCase; Priority/AssigneeId were added
--    later in camelCase (priority, assigneeId) without normalizing to the table's
--    established convention — direct evidence of ad hoc, unreviewed schema growth.
-- 3. Partition list has a finite, hardcoded horizon with a pMax catch-all, and there
--    is no automated job anywhere in this codebase that adds new partitions ahead of
--    it — illustrative of a scaling cliff with a forecastable trigger date, not tied
--    to any specific real calendar date.
CREATE TABLE IF NOT EXISTS `Task` (
    `Id` VARCHAR(36) NOT NULL,
    `Status` VARCHAR(20) NOT NULL DEFAULT 'OPEN',
    `CreatedDate` INT NOT NULL,
    `CreatedAt` DATETIME NOT NULL,
    `CompletedAt` DATETIME DEFAULT NULL,
    `priority` INT NOT NULL DEFAULT 0,
    `assigneeId` VARCHAR(36) DEFAULT NULL,
    PRIMARY KEY (`CreatedDate`, `Id`),
    INDEX `IdxAssignee` (`assigneeId`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
PARTITION BY RANGE COLUMNS(`CreatedDate`) (
    PARTITION p1 VALUES LESS THAN (20260201),
    PARTITION p2 VALUES LESS THAN (20260301),
    PARTITION p3 VALUES LESS THAN (20260401),
    PARTITION p4 VALUES LESS THAN (20260501),
    PARTITION p5 VALUES LESS THAN (20260601),
    PARTITION p6 VALUES LESS THAN (20260701),
    PARTITION pmax VALUES LESS THAN (MAXVALUE)
);
