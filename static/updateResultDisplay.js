function updateSkillsContainer(knownSkills, estimatedSkills) {
    // Prepare data
    const skillLabels = Object.keys(knownSkills);
    const knownDataPoints = Object.values(knownSkills);
    const additionalEstimatedPoints = skillLabels.map(skill => estimatedSkills[skill] - knownSkills[skill]);

    // Chart data
    const chartData = {
        labels: skillLabels,
        datasets: [{
            label: 'Known Skills',
            data: knownDataPoints,
            backgroundColor: 'rgba(75, 192, 192, 0.2)', // Green
            borderColor: 'rgba(75, 192, 192, 1)',
            borderWidth: 1
        }, {
            label: 'Additional Estimated Points',
            data: additionalEstimatedPoints,
            backgroundColor: 'rgba(255, 159, 64, 0.2)', // Orange
            borderColor: 'rgba(255, 159, 64, 1)',
            borderWidth: 1
        }]
    };

    // Options for stacked bar chart
    const options = {
        scales: {
            x: {
                stacked: true,
            },
            y: {
                stacked: true,
                beginAtZero: true
            }
        }
    };

    // Create the chart
    new Chart(document.getElementById('skillsChart'), {
        type: 'bar',
        data: chartData,
        options: options
    });
}

function displayPlayerDetails(playerDetails) {
    let detailsHtml = `<div><h2>${playerDetails.Player} / ${playerDetails.PlayerID}</h2>`;
    detailsHtml += `<p><strong>Bat Hand:</strong> ${playerDetails.BatHand}, <strong>Bowl Type:</strong> ${playerDetails.BowlType}</p>`;
    detailsHtml += `<p><strong>Talents:</strong> ${playerDetails.Talent1}${playerDetails.Talent2 ? ', ' + playerDetails.Talent2 : ''}</p>`;
    detailsHtml += `<p><strong>Birth Week:</strong> Year ${playerDetails.BirthWeek[1]}, Week ${playerDetails.BirthWeek[0]}</p></div>`;

    $('#playerDetails').html(detailsHtml); // Assumes a div with id="playerDetails" exists
}

