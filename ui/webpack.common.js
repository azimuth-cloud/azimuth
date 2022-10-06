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
            // console: require.resolve('console-browserify'),
            // constants: require.resolve('constants-browserify'),
            crypto: require.resolve('crypto-browserify'),
            // domain: require.resolve('domain-browser'),
            // events: require.resolve('events'),
            // http: require.resolve('stream-http'),
            // https: require.resolve('https-browserify'),
            // os: require.resolve('os-browserify/browser'),
            // path: require.resolve('path-browserify'),
            // punycode: require.resolve('punycode'),
            process: require.resolve('process/browser'),
            // querystring: require.resolve('querystring-es3'),
            stream: require.resolve('stream-browserify'),
            // string_decoder: require.resolve('string_decoder'),
            // sys: require.resolve('util'),
            // timers: require.resolve('timers-browserify'),
            // tty: require.resolve('tty-browserify'),
            // url: require.resolve('url'),
            // util: require.resolve('util'),
            // vm: require.resolve('vm-browserify'),
            // zlib: require.resolve('browserify-zlib')
        }
    }
};
