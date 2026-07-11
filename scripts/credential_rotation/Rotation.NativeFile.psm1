Set-StrictMode -Version Latest

if ($null -eq ('AeroOne.CredentialRotation.NativeFile' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

namespace AeroOne.CredentialRotation
{
    public static class NativeFile
    {
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool MoveFileEx(
            string existingFileName,
            string newFileName,
            uint flags
        );
    }
}
'@
}

function Move-RotationFileAtomically {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )

    $sourceIdentity = Assert-SinglePhysicalFile -Path $SourcePath
    $destinationIdentity = Assert-SinglePhysicalFile -Path $DestinationPath
    if ([string]$sourceIdentity.VolumeSerialNumber -cne [string]$destinationIdentity.VolumeSerialNumber) {
        throw 'atomic-replace-cross-volume'
    }
    if (Test-SamePhysicalObject -Left $sourceIdentity -Right $destinationIdentity) {
        throw 'atomic-replace-identity-collision'
    }
    $replaceExistingAndWriteThrough = [uint32]0x9
    if (-not [AeroOne.CredentialRotation.NativeFile]::MoveFileEx(
        $SourcePath,
        $DestinationPath,
        $replaceExistingAndWriteThrough
    )) {
        throw "atomic-replace-failed-$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
    }
}

Export-ModuleMember -Function 'Move-RotationFileAtomically'
