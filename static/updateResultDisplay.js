let skillsChart = null;

function updateSkillsContainer(playerDetails, knownSkills, estimatedSpare, estimatedMaxTraining) {
    displayPlayerDetails(playerDetails); // Assuming this function is defined elsewhere

    const skillLabels = ['Batting', 'Bowling', 'Keeping', 'Fielding', 'Endurance', 'Technique', 'Power'];
    const SKILL_LEVELS = ['atrocious', 'dreadful', 'poor', 'ordinary', 'average', 'reasonable', 'capable', 'reliable', 'accomplished', 'expert', 'outstanding', 'spectacular', 'exceptional', 'world class', 'elite', 'legendary'];

    const distributedSparePoints = estimatedSpare.map((value, index) => value === 0 ? 0 : value);
    const possibleTrainingPoints = estimatedMaxTraining.map((value, index) => estimatedSpare[index] === 0 ? value : 0);

    const chartData = {
        labels: skillLabels,
        datasets: [{
            label: 'Known Skills',
            data: knownSkills,
            backgroundColor: 'rgba(127, 201, 127, 0.7)',
        }, {
            label: 'Distributed Spare Rating',
            data: distributedSparePoints,
            backgroundColor: 'rgba(190, 174, 212, 0.7)',
        }, {
            label: 'Possible Training',
            data: possibleTrainingPoints,
            backgroundColor: 'rgba(253, 192, 134, 0.7)',
        }]
    };

    const options = {
        scales: {
            x: { stacked: true },
            y: {
                stacked: true,
                beginAtZero: true,
                ticks: {
                    // Use a custom function to convert tick values into skill level labels
                    callback: function(value, index, values) {
                        // Convert value to an index in the SKILL_LEVELS array
                        const skillIndex = value / 1000;
                        // Return the corresponding label or an empty string if out of range
                        return SKILL_LEVELS[skillIndex] || '';
                    },
                    stepSize: 1000 // Ensure we have a tick for each skill level
                }
            }
        },
        plugins: {
            legend: {
                display: true
            }
        }
    };

    if (skillsChart) {
        skillsChart.destroy(); // Destroy the existing chart
    }

    // Create a new chart instance
    skillsChart = new Chart(document.getElementById('skillsChart'), {
        type: 'bar',
        data: chartData,
        options: options
    });
}

function loadPlayerDetailsAndSkills(playerId) {
    $.ajax({
        type: 'POST',
        url: '/get_player_skills',
        data: { playerId: playerId },
        dataType: 'json',
        success: function(response) {
            updateSkillsContainer(response.player_details, response.known_skills, response.estimated_spare, response.estimated_max_training);
        }
    });
}


function displayPlayerDetails(playerDetails) {
    let detailsHtml = `<div><h2>${playerDetails.Player} / ${playerDetails.PlayerID}</h2>`;
    detailsHtml += `<p><strong>Bat Hand:</strong> ${playerDetails.BatHand}, <strong>Bowl Type:</strong> ${playerDetails.BowlType}</p>`;
    detailsHtml += `<p><strong>Talents:</strong> ${playerDetails.Talent1}${playerDetails.Talent2 ? ', ' + playerDetails.Talent2 : ''}</p>`;
    detailsHtml += `<p><strong>Birth Week:</strong> ${playerDetails.BirthWeek}</p></div>`;

    $('#playerDetails').html(detailsHtml); // Assumes a div with id="playerDetails" exists
}

