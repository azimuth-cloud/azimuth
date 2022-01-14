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
                test: /\.css$/,
                use: ["css-loader"]
            }
        ]
    },
    plugins: [
        new HtmlWebpackPlugin({
            title: 'Cloud Portal',
            template: 'assets/index.template.html',
            hash: true,
            favicon: "./src/favicon.png"
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
                filepath: './assets/tweaks.css',
                typeOfAsset: 'css',
                hash: true,
                includeSourcemap: false
            }
        ])
    ]
};
