document.addEventListener('DOMContentLoaded', function () {
    const socket = window.socket;
    const regressionPlotDOM = document.getElementById('regression-plot');
    const metricsPlotDOM = document.getElementById('metrics-plot');
    const lossPlotDOM = document.getElementById('loss-plot');

    // Initialize regression plot
    Plotly.newPlot(regressionPlotDOM, [], {
        xaxis: { title: 'Feature (X)', zeroline: true },
        yaxis: { title: 'Target (Y)', zeroline: true },
        margin: { t: 30, b: 40, l: 50, r: 20 },
        legend: { x: 1, xanchor: 'right', y: 1 },
        displayModeBar: false,
        responsive: true,
    });

    // Initialize metrics plot (2x2 grid)
    Plotly.newPlot(metricsPlotDOM, [
        { x: [], y: [], type: 'scatter', xaxis: 'x1', yaxis: 'y1' },
        { x: [], y: [], type: 'scatter', xaxis: 'x2', yaxis: 'y2' },
        { x: [], y: [], type: 'scatter', xaxis: 'x3', yaxis: 'y3' },
        { x: [], y: [], type: 'scatter', xaxis: 'x4', yaxis: 'y4' },
    ], {
        grid: { rows: 2, columns: 2, pattern: 'independent' },
        showlegend: false,
        margin: { l: 60, r: 60, b: 30, t: 30, pad: 4 },
        xaxis: { title: 'epochs' }, yaxis: { title: 'R2' },
        xaxis2: { title: 'epochs' }, yaxis2: { title: 'MSE' },
        xaxis3: { title: 'epochs' }, yaxis3: { title: 'RMSE' },
        xaxis4: { title: 'epochs' }, yaxis4: { title: 'MAE' },
    }, { displayModeBar: false, responsive: true });

    // Initialize loss plot
    Plotly.newPlot(lossPlotDOM, [{ x: [], y: [], type: 'scatter', name: 'loss' }], {
        showlegend: false,
        xaxis: { title: 'Epoch' },
        yaxis: { title: 'Loss' },
        margin: { t: 20, b: 40, l: 60, r: 20 },
    }, { displayModeBar: false, responsive: true });

    // WebSocket message handler
    socket.onmessage = function (event) {
        console.log('[playground] WS message received');
        const data = JSON.parse(event.data);
        console.log('[playground] task:', data.task);

        const progressBarDOM = document.getElementById('training-progress');
        const statusDOM = document.getElementById('training-status');

        if (data.task === 'error') {
            statusDOM.textContent = 'Error: ' + data.message;
            console.error('[playground] Backend error:', data.message);
            return;
        }

        if (data.task === 'prepare_model') {
            statusDOM.textContent = 'Model prepared. Ready to train.';
            document.getElementById('train-model-btn').disabled = false;
            console.log('[playground] Model prepared successfully');
            return;
        }

        if (data.task === 'training_complete') {
            progressBarDOM.value = 100;
            statusDOM.textContent = 'Training complete!';
            document.getElementById('train-model-btn').disabled = false;
            console.log('[playground] Training complete');
        }

        if (data.task === 'update_plot' || data.task === 'training_complete') {
            // Update regression scatter + prediction line
            const datasetTrace = {
                name: 'Data', mode: 'markers', type: 'scatter',
                x: data.x_data, y: data.y_data,
            };
            const predictionTrace = {
                name: 'Prediction', mode: 'lines', type: 'scatter',
                x: data.x_plot, y: data.y_pred,
            };
            Plotly.react(regressionPlotDOM, [datasetTrace, predictionTrace], regressionPlotDOM.layout);

            // Update metrics values
            if (data.r2 !== undefined) document.getElementById('r2-metric').textContent = data.r2.toFixed(4);
            if (data.mse !== undefined) document.getElementById('mse-metric').textContent = data.mse.toFixed(4);
            if (data.rmse !== undefined) document.getElementById('rmse-metric').textContent = data.rmse.toFixed(4);
            if (data.mae !== undefined) document.getElementById('mae-metric').textContent = data.mae.toFixed(4);

            // Update metrics plot
            if (data.epochs && data.r2_values) {
                Plotly.react(metricsPlotDOM, [
                    { x: data.epochs, y: data.r2_values, type: 'scatter', xaxis: 'x1', yaxis: 'y1' },
                    { x: data.epochs, y: data.mse_values, type: 'scatter', xaxis: 'x2', yaxis: 'y2' },
                    { x: data.epochs, y: data.rmse_values, type: 'scatter', xaxis: 'x3', yaxis: 'y3' },
                    { x: data.epochs, y: data.mae_values, type: 'scatter', xaxis: 'x4', yaxis: 'y4' },
                ], metricsPlotDOM.layout, { displayModeBar: false });
            }

            // Update loss plot
            if (data.epochs && data.loss_values) {
                Plotly.react(lossPlotDOM, [{ x: data.epochs, y: data.loss_values, type: 'scatter', name: 'loss' }], lossPlotDOM.layout);
            }

            // Update progress
            if (data.current_epoch && data.total_epochs) {
                const progress = Math.round((data.current_epoch / data.total_epochs) * 100);
                progressBarDOM.value = progress;
                statusDOM.textContent = 'Epoch ' + data.current_epoch + ' / ' + data.total_epochs;
            }
        }
    };

    console.log('[playground] Initialized, socket readyState:', socket.readyState);
});

// Prepare model: send dataset + params to backend via WebSocket
function prepareModel(event) {
    event.preventDefault();

    const socket = window.socket;
    const depVar = document.getElementById('dependent-variable').value;
    const indepVar = document.getElementById('independent-variable').value;
    const algorithmSelect = document.getElementById('algorithm-select');
    const algorithmName = algorithmSelect ? algorithmSelect.value : 'linear_regression';

    console.log('[playground] prepareModel: algorithm=' + algorithmName + ' dep=' + depVar + ' indep=' + indepVar);

    if (!depVar || !indepVar) {
        alert('Please select both target and feature variables.');
        return;
    }

    const datasetFile = window.dataset;
    if (!datasetFile) {
        alert('Please select or upload a dataset first.');
        return;
    }

    // Collect algorithm params from the form (loaded via HTMX)
    const paramForm = document.getElementById('algorithm-params-form');
    const params = {};
    if (paramForm) {
        const formData = new FormData(paramForm);
        for (const [key, value] of formData.entries()) {
            if (value === '') continue; // skip empty fields
            const num = Number(value);
            params[key] = !isNaN(num) ? num : value;
        }
        // Handle unchecked checkboxes (not in FormData)
        paramForm.querySelectorAll('input[type="checkbox"]').forEach(function (cb) {
            if (!cb.checked) params[cb.name] = false;
            else if (!(cb.name in params)) params[cb.name] = true;
        });
    }

    console.log('[playground] Collected params:', params);

    document.getElementById('training-status').textContent = 'Preparing model...';
    document.getElementById('training-progress').value = 0;

    const reader = new FileReader();
    reader.onload = function (e) {
        const message = {
            task: 'prepare_model',
            algorithm: algorithmName,
            dependent_variable: depVar,
            independent_variable: indepVar,
            params: params,
            dataset: e.target.result,
        };
        console.log('[playground] Sending prepare_model, dataset size:', e.target.result.length);
        socket.send(JSON.stringify(message));
    };
    reader.readAsText(datasetFile);
}

// Train model: send train command via WebSocket
function trainModel(event) {
    event.preventDefault();

    const socket = window.socket;
    document.getElementById('training-status').textContent = 'Training...';
    document.getElementById('train-model-btn').disabled = true;

    console.log('[playground] Sending train_model');
    socket.send(JSON.stringify({ task: 'train_model' }));
}
