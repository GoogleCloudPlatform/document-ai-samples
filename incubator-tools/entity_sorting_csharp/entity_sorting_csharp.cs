using System;
using System.Collections.Generic;
using System.Linq;

public class EntitySorter
{
    public static Dictionary<string, object> EntityOrdering(Dictionary<string, object> jsonContent)
    {
        if (jsonContent.ContainsKey("entities") && jsonContent["entities"] is List<Dictionary<string, object>> entities)
        {
            // Sorting children
            foreach (var entity in entities)
            {
                if (entity.ContainsKey("properties") && entity["properties"] is List<Dictionary<string, object>> properties)
                {
                    properties.Sort((a, b) =>
                    {
                        var x = GetNormalizedX(a);
                        var y = GetNormalizedX(b);
                        return x.CompareTo(y);
                    });
                    entity["properties"] = properties;
                }
            }

            var entitiesByPage = new List<List<Dictionary<string, object>>>();
            for (int i = 0; i < entities.Count; i++)
            {
                var pageRef = GetPageRef(entities[i]);
                int pageNumber = pageRef.ContainsKey("page") ? Convert.ToInt32(pageRef["page"]) : 0;
                if (pageNumber >= entitiesByPage.Count)
                {
                    for (int j = entitiesByPage.Count; j <= pageNumber; j++)
                    {
                        entitiesByPage.Add(new List<Dictionary<string, object>>());
                    }
                }
                entitiesByPage[pageNumber].Add(entities[i]);
            }

            // Sorting entities
            var entitiesArray = new List<Dictionary<string, object>>();
            foreach (var page in entitiesByPage)
            {
                var sortArray = new List<Dictionary<string, object>>();
                foreach (var item in page)
                {
                    sortArray.Add(new Dictionary<string, object>
                    {
                        { "y", GetNormalizedY(item) },
                        { "entity", item }
                    });
                }

                sortArray = sortArray.OrderBy(item => GetNormalizedY(item["entity"])).ToList();
                entitiesArray.AddRange(sortArray.Select(item => item["entity"] as Dictionary<string, object>));
            }
            jsonContent["entities"] = entitiesArray;
        }

        return jsonContent;
    }

    private static double GetNormalizedX(Dictionary<string, object> entity)
    {
        if (entity.ContainsKey("properties") && entity["properties"] is List<Dictionary<string, object>> properties)
        {
            return GetNormalizedX(properties[0]);
        }
        return Convert.ToDouble(GetNormalizedY(GetPageRef(entity)));
    }

    private static double GetNormalizedY(Dictionary<string, object> entity)
    {
        return Convert.ToDouble(entity["normalizedVertices"][0]["y"]);
    }

    private static Dictionary<string, object> GetPageRef(Dictionary<string, object> entity)
    {
        if (entity.ContainsKey("properties") && entity["properties"] is List<Dictionary<string, object>> properties)
        {
            var pageRef = properties[0]["pageAnchor"]["pageRefs"][0];
            return pageRef;
        }
        return entity["pageAnchor"]["pageRefs"][0];
    }
}