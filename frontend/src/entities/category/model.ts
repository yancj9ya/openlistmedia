import type { CategoryTreeDto, CategoryTreeNode } from '../../shared/api/types';

export interface CategoryBrowserModel {
  path: string;
  parentPath: string | null;
  root: string;
  children: CategoryTreeNode[];
  skipDirectories: string[];
}

export function toCategoryBrowserModel(dto: CategoryTreeDto): CategoryBrowserModel {
  return {
    path: dto.path,
    parentPath: dto.parent_path,
    root: dto.root,
    children: dto.children,
    skipDirectories: dto.skip_directories,
  };
}