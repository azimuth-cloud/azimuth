const webpack = require('webpack');
const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const AddAssetHtmlPlugin = require('add-asset-html-webpack-plugin');

module.exports = {
    entry: './src/main.js',
    output: {
        filename: 'bundle.js',
        path: path.resolve(__dirname, 'dist'),
        publicPath: '/'
    },
    module: {
        rules: [
            {
                test: /\.js$/,
                exclude: /node_modules/,
                use: {
                    loader: "babel-loader",
                    options: {
                        "presets": [
                            "@babel/preset-env",
                            "@babel/preset-react"
                        ],
                        "plugins": [
                            "@babel/plugin-proposal-object-rest-spread",
                            "@babel/plugin-proposal-class-properties"
                        ]
                    }
                }
            },
            {
                test: /\.css$/i,
                use: ["style-loader", "css-loader"]
            },
            {
                test: /\.(png|svg|jpg|jpeg|gif)$/i,
                use: ["file-loader"]
            }
        ]
    },
    plugins: [
        // Work around for Buffer is undefined
        // https://github.com/webpack/changelog-v5/issues/10
        // Required for sshpk
        new webpack.ProvidePlugin({
            Buffer: ['buffer', 'Buffer'],
	    process: 'process/browser.js',
        }),
        new HtmlWebpackPlugin({
            title: 'Cloud Portal',
            template: 'assets/index.template.html',
            favicon: 'assets/favicon.ico',
            hash: true
        }),
        // Add CSS links with hashes for cache busting
        new AddAssetHtmlPlugin([
            {
                filepath: './assets/bootstrap.css',
                typeOfAsset: 'css',
                hash: true,
                includeSourcemap: false
            },
            {
                filepath: './assets/pulse-overrides.css',
                typeOfAsset: 'css',
                hash: true,
                includeSourcemap: false
            },
            {
                filepath: './assets/tweaks.css',
                typeOfAsset: 'css',
                hash: true,
                includeSourcemap: false
            }
        ])
    ],
    resolve: {
        fallback: {
            assert: require.resolve('assert'),
            buffer: require.resolve('buffer'),
            crypto: require.resolve('crypto-browserify'),
            process: require.resolve('process/browser.js'),
            stream: require.resolve('stream-browserify'),
            vm: require.resolve('vm-browserify')
        }
    }
};
