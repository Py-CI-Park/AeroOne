Set-StrictMode -Version Latest

function Assert-CredentialViewerProperties {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string[]]$Expected
    )

    $actual = @($Value.PSObject.Properties.Name | Sort-Object)
    $required = @($Expected | Sort-Object)
    if (@(Compare-Object -ReferenceObject $required -DifferenceObject $actual -CaseSensitive).Count -ne 0) {
        throw 'credential-bundle-schema-invalid'
    }
}

function Assert-CredentialViewerString {
    param($Value, [int]$MinimumLength)

    if ($Value -isnot [string] -or $Value.Length -lt $MinimumLength) {
        throw 'credential-bundle-schema-invalid'
    }
}

function Assert-CredentialViewerBundle {
    param([Parameter(Mandatory = $true)]$Bundle)

    Assert-CredentialViewerProperties -Value $Bundle -Expected @(
        'rotation_id', 'database_id', 'admin_username', 'jwt_secret_key', 'users'
    )
    $parsed = [Guid]::Empty
    if (-not [Guid]::TryParse([string]$Bundle.rotation_id, [ref]$parsed) -or
        -not [Guid]::TryParse([string]$Bundle.database_id, [ref]$parsed)) {
        throw 'credential-bundle-schema-invalid'
    }
    Assert-CredentialViewerString -Value $Bundle.admin_username -MinimumLength 1
    Assert-CredentialViewerString -Value $Bundle.jwt_secret_key -MinimumLength 32
    $users = @($Bundle.users)
    if ($users.Count -eq 0) {
        throw 'credential-bundle-schema-invalid'
    }
    $usernames = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    $passwords = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($credential in $users) {
        Assert-CredentialViewerProperties -Value $credential -Expected @('username', 'password')
        Assert-CredentialViewerString -Value $credential.username -MinimumLength 1
        Assert-CredentialViewerString -Value $credential.password -MinimumLength 24
        if (-not $usernames.Add([string]$credential.username) -or
            -not $passwords.Add([string]$credential.password)) {
            throw 'credential-bundle-schema-invalid'
        }
    }
    if (@($users | Where-Object { $_.username -ceq $Bundle.admin_username }).Count -ne 1) {
        throw 'credential-bundle-schema-invalid'
    }
}

function Get-ExactCredentialViewerPath {
    param(
        [Parameter(Mandatory = $true)][string]$WorkspaceRoot,
        [Parameter(Mandatory = $true)][bool]$TestMode
    )

    $secureRoot = if ($TestMode) {
        Join-Path $WorkspaceRoot '.rotation-secure'
    } else {
        Join-Path $env:USERPROFILE 'AeroOne-secure\incident-20260710'
    }
    if (-not (Test-Path -LiteralPath $secureRoot -PathType Container)) {
        throw 'credential-viewer-root-missing'
    }
    Assert-NoReparseComponents -Path $secureRoot
    $rootIdentity = Get-PhysicalPathIdentity -Path $secureRoot
    if (-not $rootIdentity.IsDirectory) {
        throw 'credential-viewer-root-invalid'
    }
    Assert-SecureAcl -Path $secureRoot
    $credentialPath = Join-Path $secureRoot '1.12.3-credentials.dpapi'
    $credentialIdentity = Assert-SinglePhysicalFile -Path $credentialPath
    Assert-PhysicalContainment -RootIdentity $rootIdentity -ChildIdentity $credentialIdentity
    Assert-SecureAcl -Path $credentialPath
    return $credentialPath
}

function Read-ValidatedCredentialViewerBundle {
    param([Parameter(Mandatory = $true)][string]$Path)

    $bundle = Read-ProtectedJson -Path $Path -Purpose 'credential-bundle'
    Assert-CredentialViewerBundle -Bundle $bundle
    return $bundle
}

function Clear-RotationOwnedClipboard {
    param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$Expected)

    if ([string]::IsNullOrEmpty($Expected)) {
        return $true
    }
    try {
        if (-not [Windows.Clipboard]::ContainsText() -or
            [Windows.Clipboard]::GetText() -cne $Expected) {
            return $true
        }
        [Windows.Clipboard]::Clear()
        return $true
    } catch {
        return $false
    }
}

function Show-CredentialViewerWindow {
    param([Parameter(Mandatory = $true)]$Bundle)

    Add-Type -AssemblyName PresentationFramework
    Add-Type -AssemblyName PresentationCore
    Add-Type -AssemblyName WindowsBase
    $xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="AeroOne Credential Handoff" Width="620" Height="430"
        WindowStartupLocation="CenterScreen" ResizeMode="NoResize"
        Background="#F3F6FA" FontFamily="Segoe UI">
  <Grid Margin="32">
    <Border Background="White" BorderBrush="#D7E0EA" BorderThickness="1" CornerRadius="16" Padding="28">
      <StackPanel>
        <TextBlock Text="Credential handoff" FontSize="24" FontWeight="SemiBold" Foreground="#122033" />
        <TextBlock Text="Passwords are protected for the current Windows account." Margin="0,8,0,24" FontSize="13" Foreground="#52657A" />
        <TextBlock Text="Account" FontSize="12" FontWeight="SemiBold" Foreground="#334A62" />
        <ComboBox x:Name="AccountSelector" Height="36" Margin="0,7,0,18" Padding="10,5" />
        <TextBlock Text="Password" FontSize="12" FontWeight="SemiBold" Foreground="#334A62" />
        <Grid Margin="0,7,0,10">
          <PasswordBox x:Name="MaskedPassword" Height="38" Padding="10,7" IsHitTestVisible="False" Focusable="False" />
          <TextBox x:Name="RevealedPassword" Height="38" Padding="10,7" IsReadOnly="True" Visibility="Collapsed" />
        </Grid>
        <DockPanel Margin="0,0,0,18">
          <CheckBox x:Name="RevealPassword" Content="Reveal password" VerticalAlignment="Center" />
          <Button x:Name="CopyPassword" Content="Copy password" DockPanel.Dock="Right" Width="132" Height="34" HorizontalAlignment="Right" Background="#1769E0" Foreground="White" BorderThickness="0" />
        </DockPanel>
        <Border Background="#FFF6E5" BorderBrush="#F4D18A" BorderThickness="1" CornerRadius="8" Padding="12">
          <TextBlock Text="The clipboard is cleared after 30 seconds if it still contains the copied password." TextWrapping="Wrap" FontSize="12" Foreground="#6A4A10" />
        </Border>
        <TextBlock x:Name="StatusText" Margin="0,14,0,0" FontSize="12" Foreground="#52657A" />
      </StackPanel>
    </Border>
  </Grid>
</Window>
'@
    $window = [Windows.Markup.XamlReader]::Parse($xaml)
    $accountSelector = $window.FindName('AccountSelector')
    $maskedPassword = $window.FindName('MaskedPassword')
    $revealedPassword = $window.FindName('RevealedPassword')
    $revealPassword = $window.FindName('RevealPassword')
    $copyPassword = $window.FindName('CopyPassword')
    $statusText = $window.FindName('StatusText')
    $credentials = @{}
    foreach ($credential in @($Bundle.users)) {
        $credentials[[string]$credential.username] = [string]$credential.password
    }
    $state = [PSCustomObject]@{ ClipboardText = ''; ClearAttempts = 0 }
    $timer = New-Object Windows.Threading.DispatcherTimer
    $timer.Interval = [TimeSpan]::FromSeconds(30)
    $timer.Add_Tick({
        if (Clear-RotationOwnedClipboard -Expected $state.ClipboardText) {
            $timer.Stop()
            $state.ClipboardText = ''
            $statusText.Text = 'Clipboard cleared.'
        } else {
            $state.ClearAttempts += 1
            $timer.Interval = [TimeSpan]::FromSeconds(1)
            if ($state.ClearAttempts -ge 5) {
                $timer.Stop()
                $state.ClipboardText = ''
                $statusText.Text = 'Clipboard could not be cleared automatically.'
            }
        }
    })
    $accountSelector.ItemsSource = @($Bundle.users | ForEach-Object { [string]$_.username })
    $accountSelector.Add_SelectionChanged({
        $selected = [string]$accountSelector.SelectedItem
        $password = [string]$credentials[$selected]
        $maskedPassword.Password = $password
        $revealedPassword.Text = $password
        $revealPassword.IsChecked = $false
        $revealedPassword.Visibility = [Windows.Visibility]::Collapsed
        $maskedPassword.Visibility = [Windows.Visibility]::Visible
        $statusText.Text = if ($selected -ceq $Bundle.admin_username) { 'Configured administrator' } else { '' }
    })
    $revealPassword.Add_Checked({
        $maskedPassword.Visibility = [Windows.Visibility]::Collapsed
        $revealedPassword.Visibility = [Windows.Visibility]::Visible
    })
    $revealPassword.Add_Unchecked({
        $revealedPassword.Visibility = [Windows.Visibility]::Collapsed
        $maskedPassword.Visibility = [Windows.Visibility]::Visible
    })
    $copyPassword.Add_Click({
        $selected = [string]$accountSelector.SelectedItem
        $password = [string]$credentials[$selected]
        [Windows.Clipboard]::SetText($password)
        $state.ClipboardText = $password
        $state.ClearAttempts = 0
        $timer.Interval = [TimeSpan]::FromSeconds(30)
        $timer.Start()
        $statusText.Text = 'Copied. Clipboard clear scheduled.'
    })
    $window.Add_Closed({
        $timer.Stop()
        $null = Clear-RotationOwnedClipboard -Expected $state.ClipboardText
        $maskedPassword.Password = ''
        $revealedPassword.Text = ''
        $state.ClipboardText = ''
        $credentials.Clear()
    })
    $accountSelector.SelectedItem = [string]$Bundle.admin_username
    $null = $window.ShowDialog()
}

Export-ModuleMember -Function @(
    'Get-ExactCredentialViewerPath',
    'Read-ValidatedCredentialViewerBundle',
    'Show-CredentialViewerWindow'
)
