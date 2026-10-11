const webpack = require('webpack');
const { merge } = require('webpack-merge');
const path = require('path');

module.exports = merge(
    require('./webpack.common.js'),
    {
        devtool: 'inline-source-map',
        plugins: [
            new webpack.DefinePlugin({
                'process.env': {
                    'NODE_ENV': JSON.stringify('development')
                }
            }),
        ],
        devServer: {
            // contentBase: path.join(__dirname, 'dist'),
            compress: true,
            port: 3000,
            // disableHostCheck: true,
            historyApiFallback: true,
            proxy: [
                {
                    context: ['/api', '/auth', '/static'],
                    target: 'http://127.0.0.1:8000',
                    changeOrigin: false
                }
            ]
        }
    }
);
