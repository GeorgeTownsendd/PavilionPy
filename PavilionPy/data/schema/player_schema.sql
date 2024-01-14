CREATE TABLE Players (
    PlayerID VARCHAR(255),
    Player VARCHAR(255),
    Nationality VARCHAR(255),
    Age FLOAT,
    CountryOfResidence VARCHAR(255),
    TeamID INT,
    TeamName VARCHAR(255),
    Batting INT,
    Bowling INT,
    Fielding INT,
    Keeping INT,
    Technique INT,
    Power INT,
    Endurance INT,
    Rating INT,
    SummaryAllr INT,
    SummaryBat INT,
    SummaryBowl INT,
    SummaryKeep INT,
    BatHand VARCHAR(255),
    BowlType VARCHAR(255),
    Talent1 VARCHAR(255),
    Talent2 VARCHAR(255),
    Captaincy INT,
    Experience INT,
    Form INT,
    WageDiscount FLOAT,
    WagePaid INT,
    WageReal INT,
    BiddingTeam VARCHAR(255),
    BiddingTeamID INT,
    CurrentBid INT,
    NatSquad BOOLEAN,
    Fatigue VARCHAR(255),
    Training VARCHAR(255),
    Touring BOOLEAN,
    TrainingWeek INT,
    AgeYear INT,
    AgeWeeks INT,
    AgeDisplay FLOAT,
    AgeValue FLOAT,
    DataTimestamp DATETIME,
    DataSeason INT,
    DataWeek INT,
    Deadline DATETIME,
    PRIMARY KEY (PlayerID)
);
