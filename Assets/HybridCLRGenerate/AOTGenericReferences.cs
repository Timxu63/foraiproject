using System.Collections.Generic;
public class AOTGenericReferences : UnityEngine.MonoBehaviour
{

	// {{ AOT assemblies
	public static readonly IReadOnlyList<string> PatchedAOTAssemblyList = new List<string>
	{
		"ForAI.Project.Runtime.dll",
		"mscorlib.dll",
	};
	// }}

	// {{ constraint implement type
	// }} 

	// {{ AOT generic types
	// System.Action<ForAI.Project.HotUpdate.Features.Inventory.Application.InventoryItemViewData>
	// System.Collections.Generic.ArraySortHelper<ForAI.Project.HotUpdate.Features.Inventory.Application.InventoryItemViewData>
	// System.Collections.Generic.Comparer<ForAI.Project.HotUpdate.Features.Inventory.Application.InventoryItemViewData>
	// System.Collections.Generic.ICollection<ForAI.Project.HotUpdate.Features.Inventory.Application.InventoryItemViewData>
	// System.Collections.Generic.IComparer<ForAI.Project.HotUpdate.Features.Inventory.Application.InventoryItemViewData>
	// System.Collections.Generic.IEnumerable<ForAI.Project.HotUpdate.Features.Inventory.Application.InventoryItemViewData>
	// System.Collections.Generic.IEnumerator<ForAI.Project.HotUpdate.Features.Inventory.Application.InventoryItemViewData>
	// System.Collections.Generic.IList<ForAI.Project.HotUpdate.Features.Inventory.Application.InventoryItemViewData>
	// System.Collections.Generic.List.Enumerator<ForAI.Project.HotUpdate.Features.Inventory.Application.InventoryItemViewData>
	// System.Collections.Generic.List<ForAI.Project.HotUpdate.Features.Inventory.Application.InventoryItemViewData>
	// System.Collections.Generic.ObjectComparer<ForAI.Project.HotUpdate.Features.Inventory.Application.InventoryItemViewData>
	// System.Collections.ObjectModel.ReadOnlyCollection<ForAI.Project.HotUpdate.Features.Inventory.Application.InventoryItemViewData>
	// System.Comparison<ForAI.Project.HotUpdate.Features.Inventory.Application.InventoryItemViewData>
	// System.Predicate<ForAI.Project.HotUpdate.Features.Inventory.Application.InventoryItemViewData>
	// }}

	public void RefMethods()
	{
		// ForAI.Project.HotUpdate.Features.Inventory.UI.InventoryScreenArgs ForAI.Project.Runtime.UI.Core.UIOpenContext.GetArgs<ForAI.Project.HotUpdate.Features.Inventory.UI.InventoryScreenArgs>()
		// object& System.Runtime.CompilerServices.Unsafe.As<object,object>(object&)
		// System.Void* System.Runtime.CompilerServices.Unsafe.AsPointer<object>(object&)
	}
}