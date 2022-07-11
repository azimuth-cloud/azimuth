import React from 'react';

import Image from 'react-bootstrap/Image';

import StackHPCLogo from './StackHPC_logo.png';


export const Footer = () => (
    <div className="sticky-footer">
        <a href="https://github.com/stackhpc/azimuth" target="_blank">Azimuth</a>,{" "}
        supported by{" "}
        <a href="https://stackhpc.com" target="_blank">
            <Image src={StackHPCLogo} title="StackHPC" />
        </a>
    </div>
);
