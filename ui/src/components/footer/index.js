import React from 'react';

import Image from 'react-bootstrap/Image';

import AzimuthLogo from './azimuth-logo-blue-text.png';


export const Footer = () => (
    <div className="sticky-footer">
        <a href="https://github.com/azimuth-cloud/azimuth" target="_blank">
            <Image src={AzimuthLogo} title="Azimuth" />
        </a>
    </div>
);
