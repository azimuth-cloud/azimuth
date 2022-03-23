/**
 * This module contains components for the tenancy Kubernetes clusters page.
 */

import React from 'react';

import { usePageTitle } from '../../../utils';

import { useResourceInitialised, ResourcePanel } from '../resource-utils';
import { KubernetesClustersTable } from './table';
import { CreateKubernetesClusterButton } from './create-button';


const KubernetesClusters = ({ resourceData, resourceActions, ...props }) => (
    <KubernetesClustersTable
        kubernetesClusters={resourceData}
        kubernetesClusterActions={resourceActions}
        {...props}
    />
);


export const TenancyKubernetesClustersPanel = ({ tenancy, tenancyActions }) => {
    usePageTitle('Kubernetes');
    useResourceInitialised(tenancy.sizes, tenancyActions.size.fetchList);
    useResourceInitialised(
        tenancy.kubernetesClusterTemplates,
        tenancyActions.kubernetesClusterTemplate.fetchList
    );
    return (
        <ResourcePanel
            resource={tenancy.kubernetesClusters}
            resourceActions={tenancyActions.kubernetesCluster}
            resourceName="Kubernetes clusters"
            createButtonComponent={CreateKubernetesClusterButton}
            createButtonExtraProps={({
                kubernetesClusterTemplates: tenancy.kubernetesClusterTemplates,
                kubernetesClusterTemplateActions: tenancyActions.kubernetesClusterTemplate,
                sizes: tenancy.sizes,
                sizeActions: tenancyActions.size
            })}
        >
            <KubernetesClusters
                kubernetesClusterTemplates={tenancy.kubernetesClusterTemplates}
                kubernetesClusterTemplateActions={tenancyActions.kubernetesClusterTemplate}
                sizes={tenancy.sizes}
                sizeActions={tenancyActions.size}
            />
        </ResourcePanel>
    );
};
