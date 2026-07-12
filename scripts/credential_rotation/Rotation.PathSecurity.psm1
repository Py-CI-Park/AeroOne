Set-StrictMode -Version Latest

if ($null -eq ('AeroOne.CredentialRotation.NativePath' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;

namespace AeroOne.CredentialRotation
{
    [StructLayout(LayoutKind.Sequential)]
    internal struct ByHandleFileInformation
    {
        internal uint FileAttributes;
        internal System.Runtime.InteropServices.ComTypes.FILETIME CreationTime;
        internal System.Runtime.InteropServices.ComTypes.FILETIME LastAccessTime;
        internal System.Runtime.InteropServices.ComTypes.FILETIME LastWriteTime;
        internal uint VolumeSerialNumber;
        internal uint FileSizeHigh;
        internal uint FileSizeLow;
        internal uint NumberOfLinks;
        internal uint FileIndexHigh;
        internal uint FileIndexLow;
    }

    public sealed class PathIdentity
    {
        public string FinalPath { get; private set; }
        public uint VolumeSerialNumber { get; private set; }
        public ulong FileId { get; private set; }
        public uint LinkCount { get; private set; }
        public bool IsDirectory { get; private set; }

        internal PathIdentity(
            string finalPath,
            uint volumeSerialNumber,
            ulong fileId,
            uint linkCount,
            bool isDirectory)
        {
            FinalPath = finalPath;
            VolumeSerialNumber = volumeSerialNumber;
            FileId = fileId;
            LinkCount = linkCount;
            IsDirectory = isDirectory;
        }
    }

    public static class NativePath
    {
        private const uint FileReadAttributes = 0x80;
        private const uint ShareAll = 0x7;
        private const uint OpenExisting = 3;
        private const uint BackupSemantics = 0x02000000;
        private const uint DirectoryAttribute = 0x10;

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern SafeFileHandle CreateFileW(
            string fileName,
            uint desiredAccess,
            uint shareMode,
            IntPtr securityAttributes,
            uint creationDisposition,
            uint flagsAndAttributes,
            IntPtr templateFile);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern uint GetFinalPathNameByHandleW(
            SafeFileHandle file,
            StringBuilder path,
            uint pathLength,
            uint flags);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool GetFileInformationByHandle(
            SafeFileHandle file,
            out ByHandleFileInformation information);

        public static PathIdentity Inspect(string path)
        {
            bool directory = Directory.Exists(path);
            uint flags = directory ? BackupSemantics : 0;
            using (SafeFileHandle handle = CreateFileW(
                path,
                FileReadAttributes,
                ShareAll,
                IntPtr.Zero,
                OpenExisting,
                flags,
                IntPtr.Zero))
            {
                if (handle.IsInvalid)
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                }
                ByHandleFileInformation information;
                if (!GetFileInformationByHandle(handle, out information))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                }
                StringBuilder buffer = new StringBuilder(32768);
                uint length = GetFinalPathNameByHandleW(handle, buffer, (uint)buffer.Capacity, 0);
                if (length == 0 || length >= buffer.Capacity)
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                }
                string finalPath = NormalizeFinalPath(buffer.ToString());
                ulong fileId = ((ulong)information.FileIndexHigh << 32) | information.FileIndexLow;
                bool isDirectory = (information.FileAttributes & DirectoryAttribute) != 0;
                return new PathIdentity(
                    finalPath,
                    information.VolumeSerialNumber,
                    fileId,
                    information.NumberOfLinks,
                    isDirectory);
            }
        }

        private static string NormalizeFinalPath(string path)
        {
            const string uncPrefix = @"\\?\UNC\";
            const string localPrefix = @"\\?\";
            if (path.StartsWith(uncPrefix, StringComparison.OrdinalIgnoreCase))
            {
                return @"\\" + path.Substring(uncPrefix.Length);
            }
            if (path.StartsWith(localPrefix, StringComparison.OrdinalIgnoreCase))
            {
                return path.Substring(localPrefix.Length);
            }
            return path;
        }
    }
}
'@
}

function Assert-NoReparseComponents {
    param([Parameter(Mandatory = $true)][string]$Path)

    $fullPath = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetPathRoot($fullPath)
    $relative = $fullPath.Substring($root.Length)
    $current = $root.TrimEnd('\')
    foreach ($component in $relative.Split([char]'\', [StringSplitOptions]::RemoveEmptyEntries)) {
        $current = Join-Path $current $component
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'reparse-forbidden'
            }
        }
    }
}

function Get-PhysicalPathIdentity {
    param([Parameter(Mandatory = $true)][string]$Path)

    Assert-NoReparseComponents -Path $Path
    return [AeroOne.CredentialRotation.NativePath]::Inspect([IO.Path]::GetFullPath($Path))
}

function Assert-SinglePhysicalFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    $identity = Get-PhysicalPathIdentity -Path $Path
    if ($identity.IsDirectory -or $identity.LinkCount -ne 1) {
        throw 'hardlink-forbidden'
    }
    return $identity
}

function Test-SamePhysicalObject {
    param(
        [Parameter(Mandatory = $true)]$Left,
        [Parameter(Mandatory = $true)]$Right
    )

    return $Left.VolumeSerialNumber -eq $Right.VolumeSerialNumber -and $Left.FileId -eq $Right.FileId
}

function Assert-PhysicalContainment {
    param(
        [Parameter(Mandatory = $true)]$RootIdentity,
        [Parameter(Mandatory = $true)]$ChildIdentity
    )

    $rootPrefix = $RootIdentity.FinalPath.TrimEnd('\') + '\'
    if (-not $ChildIdentity.FinalPath.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'physical-path-escape'
    }
}

function Assert-ProductionProvenance {
    param(
        [Parameter(Mandatory = $true)][string]$WorkspaceRoot,
        [Parameter(Mandatory = $true)][string]$ProductRoot,
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [Parameter(Mandatory = $true)]
        [ValidateSet('scripts\rotate_aeroone_credentials.ps1', 'scripts\view_aeroone_credentials.ps1')]
        [string]$ExpectedEntryPoint
    )

    $workspaceIdentity = Get-PhysicalPathIdentity -Path $WorkspaceRoot
    $productIdentity = Get-PhysicalPathIdentity -Path $ProductRoot
    if (-not (Test-SamePhysicalObject -Left $workspaceIdentity -Right $productIdentity)) {
        throw 'provenance-root-mismatch'
    }
    $canonicalScript = Join-Path $WorkspaceRoot $ExpectedEntryPoint
    $canonicalIdentity = Assert-SinglePhysicalFile -Path $canonicalScript
    $scriptIdentity = Assert-SinglePhysicalFile -Path $ScriptPath
    if (-not (Test-SamePhysicalObject -Left $canonicalIdentity -Right $scriptIdentity)) {
        throw 'provenance-script-mismatch'
    }
}

Export-ModuleMember -Function @(
    'Assert-NoReparseComponents',
    'Get-PhysicalPathIdentity',
    'Assert-SinglePhysicalFile',
    'Test-SamePhysicalObject',
    'Assert-PhysicalContainment',
    'Assert-ProductionProvenance'
)
