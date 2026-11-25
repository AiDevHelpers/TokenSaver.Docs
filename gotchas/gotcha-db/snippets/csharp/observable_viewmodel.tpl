public sealed partial class {{vm_name}} : ObservableObject
{
    [ObservableProperty]
    private {{state_type}}? {{state_field}};

    [ObservableProperty]
    private bool isBusy;

    [RelayCommand]
    private async Task RefreshAsync()
    {
        if (IsBusy) return;
        IsBusy = true;
        try
        {
            // TODO(gotcha:load): call the service and assign the result
        }
        finally
        {
            IsBusy = false;
        }
    }
}
