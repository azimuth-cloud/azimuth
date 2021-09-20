/**
 * This module contains components for the tenancy Kubernetes clusters page.
 */

import React from 'react';

import { usePageTitle } from '../../utils';

import { useResourceInitialised, ResourcePanel } from './resource-utils';
import { KubernetesClustersTable } from './kubernetes-clusters-table';
import { CreateKubernetesClusterButton } from './create-kubernetes-cluster-modal';


const KubernetesClusters = ({ resourceData, resourceActions, ...props }) => (
    <KubernetesClustersTable
        kubernetesClusters={resourceData}
        kubernetesClusterActions={resourceActions}
        {...props}
    />
);


export const TenancyKubernetesClustersPanel = ({
    sshKey,
    tenancy,
    tenancyActions,
    notificationActions
}) => {
    usePageTitle('Kubernetes');
    // We need to make sure the sizes are initialised
    useResourceInitialised(tenancy.sizes, tenancyActions.size.fetchList);
    return (
        <ResourcePanel
            resource={tenancy.kubernetesClusters}
            resourceActions={tenancyActions.kubernetesCluster}
            resourceName="Kubernetes clusters"
            createButtonComponent={CreateKubernetesClusterButton}
            createButtonExtraProps={({
                sshKey,
                kubernetesClusterTemplates: tenancy.kubernetesClusterTemplates,
                kubernetesClusterTemplateActions: tenancyActions.kubernetesClusterTemplate,
                sizes: tenancy.sizes,
                sizeActions: tenancyActions.size
            })}
        >
            <KubernetesClusters
                sizes={tenancy.sizes}
                notificationActions={notificationActions}
            />
        </ResourcePanel>
    );
};
