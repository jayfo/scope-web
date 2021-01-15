const express = require('express');
const rimraf = require('rimraf')
const webpack = require('webpack');
const webpackDevMiddleware = require('webpack-dev-middleware')

const paths = require('../config/paths');
const webpackConfig = require(paths.webpackConfig);

const app = express();
const compiler = webpack(webpackConfig);

rimraf.sync(paths.appBuild);

app.use(
    webpackDevMiddleware(compiler, {
        publicPath: webpackConfig.output.publicPath,
        writeToDisk: true
    })
);

app.listen(3000, function () {
        console.log(`Listening on http://localhost:${3000}/.`)
    }
);
