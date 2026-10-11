// Babel 8 requires explicitly setting the target env to prod
// otherwise it doesn't build the app properly
process.env.NODE_ENV = 'production';

const webpack = require('webpack');
const { merge } = require('webpack-merge');
const TerserPlugin = require("terser-webpack-plugin");


module.exports = merge(
    require('./webpack.common.js'),
    {
        devtool: 'source-map',
        plugins: [
            new webpack.DefinePlugin({
                'process.env': {
                    'NODE_ENV': JSON.stringify('production')
                }
            }),
        ],
        optimization: {
            minimize: true,
            minimizer: [new TerserPlugin()]
        }
    }
);
